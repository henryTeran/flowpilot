from datetime import timedelta
from decimal import localcontext
import pytest
from app.modules.revenue import billing, scenarios
from test_revenue_billing_14a import NOW, WINDOW, ticket
from test_revenue_sources_14a import exercise
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
import app.main as main_module
from sqlalchemy.orm import Session
from app.modules.tickets.models import QueueTicket
from test_postgres_scheduling_4d import postgres_flow


def request():
    return scenarios.Request(model="constant_recorded_gross_rate_v1", observed_start=WINDOW.start, observed_end=WINDOW.end,
        projected_start=NOW+timedelta(days=1), projected_end=NOW+timedelta(days=4), currency="CHF",
        activity_fraction=dict(numerator="1", denominator="3"))


def test_exact_conditional_projection_not_official_billing_under_small_decimal_context():
    evidence = billing.calculate(WINDOW, [ticket(amount="101")], [])
    with localcontext() as context:
        context.prec = 2
        result = scenarios.calculate("own", "signed", request(), evidence)
    assert result.projected_gross_minor.numerator == "101" and result.projected_gross_minor.denominator == "2"
    assert result.unavailable_reason is None and result.evidence.ticket_amounts[0].known_gross_minor == "101"
    assert not result.retained and not result.validated_prediction and not result.action_executed
    assert result.evidence.projected_revenue is None
    zero = request().model_copy(update={"activity_fraction": request().activity_fraction.model_copy(update={"numerator": "0"})})
    assert scenarios.calculate("own", "signed", zero, evidence).projected_gross_minor.numerator == "0"


@pytest.mark.parametrize("reason", ["unknown_currency", "undated_paid_tickets", "no_selected_currency", "uncertain_amounts"])
def test_missing_or_unclassified_sources_make_projection_unavailable(reason):
    rows = [ticket(amount=None, quality="missing")] if reason == "uncertain_amounts" else [ticket(currency=None)] \
        if reason == "unknown_currency" else [] if reason == "no_selected_currency" else [ticket()]
    evidence = billing.calculate(WINDOW, rows, [])
    if reason == "undated_paid_tickets": evidence = evidence.model_copy(update={"institute_undated_paid_tickets": 1})
    result = scenarios.calculate("own", "signed", request(), evidence)
    assert result.projected_gross_minor is None and result.unavailable_reason == reason


def test_unsafe_assumptions_and_corrupted_aggregate_refused():
    evidence = billing.calculate(WINDOW, [ticket()], [])
    for change in (dict(observed_start=NOW), dict(projected_start=NOW-timedelta(microseconds=1)),
        dict(projected_end=NOW), dict(observed_start=WINDOW.start.replace(tzinfo=None)),
        dict(activity_fraction=request().activity_fraction.model_copy(update={"numerator": "4"}))):
        with pytest.raises(ValueError): scenarios.calculate("own", "signed", request().model_copy(update=change), evidence)
    with pytest.raises(ValueError): scenarios.calculate("foreign", "signed", request(), evidence)
    with pytest.raises(ValueError): scenarios.calculate("own", "", request(), evidence)
    group = evidence.ticket_amounts[0].model_copy(update={"complete_gross_minor": "999"})
    with pytest.raises(ValueError): scenarios.calculate("own", "signed", request(), evidence.model_copy(update={"ticket_amounts": (group,)}))
    for name in ("action_executed", "retained", "validated_prediction"):
        valid = scenarios.calculate("own", "signed", request(), evidence).model_dump()
        with pytest.raises(ValueError): scenarios.Scenario.model_validate({**valid, name: 0})


def test_signed_preview_recaptures_source_and_rejects_injected_billing(client, monkeypatch):
    institute, _, services = _bootstrap_reference_data(client)
    evidence = exercise(main_module.engine, institute, services[0]["id"], monkeypatch)
    payload = request().model_dump(mode="json")
    path = f"/api/v1/revenue/institutes/{institute}/scenarios/revenue-preview"
    headers = _auth_headers("responsable_institut", institute)
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["actor_id"] == "test-user" and result["evidence"]["ticket_count"] == 25
    assert result["projected_gross_minor"] is None and result["unavailable_reason"] == "undated_paid_tickets"
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        assert client.post(path, headers=_auth_headers(role, owner), json=payload).status_code == 403
    assert client.post(path, json=payload).status_code == 403
    assert client.post(path, headers=headers, json={**payload, "evidence": evidence.model_dump(mode="json")}).status_code == 422
    assert client.post(path, headers=headers, json={**payload, "actor_id": "injected"}).status_code == 422
    assert client.post(path, headers=headers, json={**payload, "observed_start": "2026-01-01"}).status_code == 422
    assert client.post(path, headers=headers, json={**payload, "projected_start": WINDOW.end.isoformat(),
        "projected_end": (WINDOW.end+timedelta(days=1)).isoformat()}).status_code == 200  # capture == start allowed
    with Session(main_module.engine) as db:
        db.delete(db.get(QueueTicket, "revenue-undated")); db.commit()
    valued = client.post(path, headers=headers, json=payload)
    assert valued.status_code == 200 and valued.json()["projected_gross_minor"] == {"numerator": "2525", "denominator": "2"}


def test_postgres_scenario_uses_actual_complete_source_and_fresh_basket_values(postgres_flow, monkeypatch):
    engine, institute, _, service = postgres_flow
    exercise(engine, institute, service, monkeypatch)
    with Session(engine) as db:
        assert scenarios.preview(db, institute, request(), "signed-manager").unavailable_reason == "undated_paid_tickets"
        db.delete(db.get(QueueTicket, "revenue-undated")); db.commit()
        result = scenarios.preview(db, institute, request(), "signed-manager")
        assert result.projected_gross_minor.numerator == "2525" and result.projected_gross_minor.denominator == "2"
        db.commit()  # finish source read lock before explicit independent update
    with Session(engine) as db:
        from decimal import Decimal
        db.get(QueueTicket, "revenue-00").total_amount = Decimal("2.01"); db.commit()
    with Session(engine) as db:
        fresh = scenarios.preview(db, institute, request(), "signed-manager")
        assert fresh.projected_gross_minor.numerator == "2625" and result.projected_gross_minor.numerator == "2525"
