from datetime import timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.revenue import sources
from app.modules.tickets.models import QueueTicket, TicketLine
from test_revenue_billing_14a import NOW
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def exercise(engine, institute, service, monkeypatch):
    monkeypatch.setattr(sources, "utcnow", lambda: NOW)
    with Session(engine) as db:
        for n in range(25):
            db.add(QueueTicket(id=f"revenue-{n:02}", institute_id=institute, ticket_number=f"R{n}", arrival_time=NOW,
                status="paid", paid_at=NOW-timedelta(days=1), currency="CHF", total_amount=Decimal("1.01")))
        db.add_all([QueueTicket(id="revenue-undated", institute_id=institute, ticket_number="undated", arrival_time=NOW, status="paid"),
            QueueTicket(id="revenue-end", institute_id=institute, ticket_number="end", arrival_time=NOW, status="paid", paid_at=NOW),
            QueueTicket(id="revenue-unpaid", institute_id=institute, ticket_number="unpaid", arrival_time=NOW, status="waiting", paid_at=NOW-timedelta(days=1))])
        db.flush()
        for n in range(25):
            db.add(TicketLine(id=f"revenue-line-{n:02}", ticket_id=f"revenue-{n:02}", service_id=service,
                quantity=2, duration_minutes=20, revenue_category="care", total=Decimal("1.01")))
        db.add(TicketLine(id="removed-revenue", ticket_id="revenue-00", service_id=service, quantity=1,
            duration_minutes=20, revenue_category="retail", total=Decimal("999"), invoice_removed_at=NOW,
            invoice_removed_by_actor="manager", invoice_removal_reason="not_performed"))
        db.commit()
        result = sources.read(db, institute, NOW-timedelta(days=2), NOW)
        assert result.ticket_count == 25 and result.active_line_count == 25
        assert result.ticket_amounts[0].known_gross_minor == "2525"
        assert result.service_mix[0].units == "50" and result.service_mix[0].amounts.known_gross_minor == "2525"
        assert result.institute_undated_paid_tickets == 1 and result.recorded_retail_attach_ratio.numerator == "0"
        alternative = sources.read(db, institute, (NOW-timedelta(days=2)).astimezone(timezone(timedelta(hours=2))), NOW)
        assert alternative.ticket_amounts == result.ticket_amounts
        return result


def test_sqlite_authoritative_cohort_and_signed_manager_api(client, monkeypatch):
    institute, _, services = _bootstrap_reference_data(client)
    result = exercise(main_module.engine, institute, services[0]["id"], monkeypatch)
    path = f"/api/v1/revenue/institutes/{institute}/billing"
    params = dict(start=result.window.start.isoformat(), end=result.window.end.isoformat())
    headers = _auth_headers("responsable_institut", institute)
    response = client.get(path, params=params, headers=headers)
    assert response.status_code == 200 and response.json()["ticket_count"] == 25
    for role, owner in [("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")]:
        assert client.get(path, params=params, headers=_auth_headers(role, owner)).status_code == 403
    assert client.get(path, params=params).status_code == 403
    assert client.get(path, params={**params, "start": "2026-01-01"}, headers=headers).status_code == 422
    assert client.get(path, params={**params, "end": (NOW+timedelta(days=1)).isoformat()}, headers=headers).status_code == 400
    assert client.post(path, json=params, headers=headers).status_code == 405


def test_postgres_authoritative_cohort(postgres_flow, monkeypatch):
    engine, institute, _, service = postgres_flow
    exercise(engine, institute, service, monkeypatch)
