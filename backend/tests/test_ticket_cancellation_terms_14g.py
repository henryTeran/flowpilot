from datetime import timedelta
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import pytest
import app.main as main_module
from app.modules.tickets import service, events, cancellation_terms
from app.modules.tickets.models import QueueTicket, TicketLine, QueueEvent
from test_revenue_billing_14a import NOW
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def seed(db, institute, service_id, identifier="snapshot-ticket"):
    db.add(QueueTicket(id=identifier, institute_id=institute, ticket_number=identifier, arrival_time=NOW,
        status="waiting", total_amount=Decimal("123.45"), currency="CHF"))
    db.flush()
    db.add(TicketLine(id=identifier+"-line", ticket_id=identifier, service_id=service_id, quantity=2,
        duration_minutes=20, unit_price=Decimal("61.725"), total=Decimal("123.45")))
    db.commit()


def exercise(engine, institute, service_id, monkeypatch):
    monkeypatch.setattr(events, "utcnow", lambda: NOW)
    monkeypatch.setattr(service, "utcnow", lambda: NOW)
    with Session(engine) as db:
        seed(db, institute, service_id)
        ticket = service.cancel_ticket(db, "snapshot-ticket", "signed-manager")
        event = db.scalar(select(QueueEvent).where(QueueEvent.ticket_id == ticket.id))
        retained = event.cancellation_terms
        assert retained["fingerprint"] == cancellation_terms.fingerprint(retained["terms"])
        terms = retained["terms"]
        assert terms["actor_id"] == "signed-manager" and terms["amount_minor"] == "12345"
        assert terms["previous_status"] == "waiting" and terms["status"] == "cancelled"
        assert terms["lines"][0]["quantity"] == 2 and terms["lines"][0]["total_minor"] == "12345"
        assert not terms["realized_revenue"] and not terms["causal_loss_proven"]
        service.cancel_ticket(db, ticket.id, "retry-actor")
        assert db.scalar(select(func.count()).select_from(QueueEvent).where(QueueEvent.ticket_id == ticket.id)) == 1
        assert event.cancellation_terms == retained
        # Independent current SQL correction cannot reprice the retained event.
        ticket.total_amount = Decimal("999"); db.get(TicketLine, ticket.id+"-line").total = Decimal("999"); db.commit()
        db.refresh(event)
        assert event.cancellation_terms == retained
        seed(db, institute, service_id, "rollback-ticket")
        original_save = service.save_ticket
        def failed_save(db, ticket):
            db.flush()
            raise RuntimeError("Owned fixture commit failure")
        monkeypatch.setattr(service, "save_ticket", failed_save)
        with pytest.raises(RuntimeError): service.cancel_ticket(db, "rollback-ticket", "signed-manager")
        db.rollback()
        monkeypatch.setattr(service, "save_ticket", original_save)
        assert db.get(QueueTicket, "rollback-ticket").status == "waiting"
        assert db.scalar(select(func.count()).select_from(QueueEvent).where(QueueEvent.ticket_id == "rollback-ticket")) == 0


def test_sqlite_snapshot_atomicity_and_signed_route(client, monkeypatch):
    institute, _, service_id, _, _ = setup(client)
    exercise(main_module.engine, institute, service_id, monkeypatch)
    with Session(main_module.engine) as db:
        seed(db, institute, service_id, "signed-route-ticket")
    response = client.patch("/api/v1/tickets/signed-route-ticket/cancel", headers=_auth_headers("responsable_institut", institute))
    assert response.status_code == 200
    with Session(main_module.engine) as db:
        event = db.scalar(select(QueueEvent).where(QueueEvent.ticket_id == "signed-route-ticket"))
        assert event.cancellation_terms["terms"]["actor_id"] == "test-user"


def test_postgres_snapshot_atomicity(postgres_flow, monkeypatch):
    engine, institute, _, service_id = postgres_flow
    exercise(engine, institute, service_id, monkeypatch)
