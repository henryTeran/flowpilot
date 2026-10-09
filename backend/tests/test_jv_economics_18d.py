from datetime import timedelta
from decimal import Decimal
import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.jv import economics
from app.modules.revenue import billing, sources
from app.modules.tickets.models import QueueTicket
from app.modules.waitlist.originals import fingerprint
from test_revenue_billing_14a import NOW
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def period(start, end, values):
    window = billing.Window(institute_id="own", start=start, end=end, captured_at=NOW)
    tickets = [billing.TicketFact(institute_id="own", ticket_id=str(i), paid_at=start, captured_at=NOW,
        currency=c, amount_minor=v, amount_quality="known" if v is not None else "missing") for i, (c, v) in enumerate(values)]
    return billing.calculate(window, tickets, [])


def capture(base, current):
    return economics.Capture(baseline=period(NOW-timedelta(days=2), NOW-timedelta(days=1), base),
        current=period(NOW-timedelta(days=1), NOW, current))


def test_exact_signed_observed_change_and_currency_separation():
    source = capture([("CHF", "10000"), ("EUR", "100")], [("CHF", "8760"), ("EUR", "150")])
    result = economics.analyze(source)
    chf, eur = result.currencies
    assert chf.difference_minor == "-1240" and chf.percent_change.model_dump() == {"numerator": "-62", "denominator": "5"}
    assert eur.difference_minor == "50" and eur.percent_change.numerator == "50"
    assert result.evidence_fingerprint == fingerprint(source.model_dump(mode="json"))
    assert result.causal_contributions == () and "causal_attribution" in result.missing_facts
    assert result == economics.analyze(source)


def test_zero_baseline_incomplete_and_unknown_currency_do_not_invent_percentages():
    empty = economics.analyze(capture([], [("CHF", "100")])).currencies[0]
    assert empty.difference_minor == "100" and empty.percent_change is None and empty.unavailable_reason == "zero_baseline"
    for source, reason in [(capture([("CHF", "100")], [("CHF", None)]), "incomplete_amounts"),
        (capture([(None, "100")], [("CHF", "100")]), "unknown_currency")]:
        value = economics.analyze(source).currencies[0]
        assert value.difference_minor is None and value.percent_change is None and value.unavailable_reason == reason


def exercise(client, engine, institute, monkeypatch):
    monkeypatch.setattr(sources, "utcnow", lambda: NOW)
    with Session(engine) as db:
        for identifier, paid, amount in [("jv-base", NOW-timedelta(days=2), "100.00"), ("jv-current", NOW-timedelta(days=1), "87.60")]:
            db.add(QueueTicket(id=identifier, institute_id=institute, ticket_number=identifier, arrival_time=paid,
                status="paid", paid_at=paid, currency="CHF", total_amount=Decimal(amount)))
        db.commit()
    request = economics.Request(baseline_start=NOW-timedelta(days=2), baseline_end=NOW-timedelta(days=1), current_start=NOW-timedelta(days=1), current_end=NOW)
    path = f"/api/v1/jv/institutes/{institute}/billing-comparison"
    headers = _auth_headers("responsable_institut", institute)
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", collect)
    try:
        response = client.post(path, json=request.model_dump(mode="json"), headers=headers)
        assert response.status_code == 200, response.text
        value = response.json()
        assert value["analysis"]["currencies"][0]["difference_minor"] == "-1240"
        decomposition = value["analysis"]["currencies"][0]["decomposition"]
        assert decomposition["volume_term_minor"]["numerator"] == "0"
        assert decomposition["basket_term_minor"]["numerator"] == "-1240"
        assert value["analysis"]["evidence_fingerprint"] == fingerprint(value["source"])
        assert value["analysis"]["fingerprint"] == fingerprint({k: v for k, v in value["analysis"].items() if k != "fingerprint"})
        assert value["source"]["baseline"]["ticket_count"] == value["source"]["current"]["ticket_count"] == 1
    finally:
        event.remove(engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"}
    for role, scope in [("accueil", institute), ("responsable_institut", "foreign")]:
        assert client.post(path, json=request.model_dump(mode="json"), headers=_auth_headers(role, scope)).status_code == 403
    for field in ("source", "amount", "actor_id", "provider"):
        assert client.post(path, json={**request.model_dump(mode="json"), field: "injected"}, headers=headers).status_code == 422
    changed = request.model_dump(mode="json"); changed["baseline_start"] = 0
    assert client.post(path, json=changed, headers=headers).status_code == 422


def test_sqlite_signed_actual_paid_periods(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    exercise(client, main_module.engine, institute, monkeypatch)


def test_actual_postgres_signed_actual_paid_periods(client, postgres_flow, monkeypatch):
    engine, institute, *_ = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, engine, institute, monkeypatch)


def test_overlapping_period_and_foreign_capture_refuse():
    with pytest.raises(ValueError):
        economics.Request(baseline_start=NOW-timedelta(days=2), baseline_end=NOW, current_start=NOW-timedelta(days=1), current_end=NOW)
    source = capture([], [])
    raw = source.model_dump(mode="json"); raw["current"]["window"]["institute_id"] = "foreign"
    with pytest.raises(ValueError, match="scope/period"):
        economics.analyze(economics.Capture.model_validate(raw))


def test_unequal_durations_undated_sources_and_false_completeness_remain_explicit():
    source = capture([("CHF", "100")], [("CHF", "200")]).model_dump(mode="json")
    source["baseline"]["window"]["start"] = (NOW-timedelta(days=3)).isoformat()
    source["baseline"]["institute_undated_paid_tickets"] = 2
    result = economics.analyze(economics.Capture.model_validate(source))
    assert not result.same_elapsed_duration
    assert result.diagnostics == ("unequal_period_durations", "undated_paid_tickets")
    assert result.currencies[0].difference_minor == "100"  # raw period totals, not a daily rate
    source["current"]["complete_sales_history"] = True
    with pytest.raises(ValueError):
        economics.analyze(economics.Capture.model_validate(source))
