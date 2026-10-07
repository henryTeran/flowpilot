from datetime import timedelta
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.revenue import booking_valuation as values
from app.modules.appointments import service, events
from app.modules.appointments.models import BookingEvent
from app.modules.appointments.schemas import AppointmentCreate
from app.modules.services.models import Service
from app.modules.gift_cards.models import GiftCardSettings
from test_revenue_billing_14a import NOW
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def exercise(engine, institute, employee, service_id, monkeypatch):
    monkeypatch.setattr(service, "utcnow", lambda: NOW)
    monkeypatch.setattr(events, "utcnow", lambda: NOW)
    monkeypatch.setattr(values, "utcnow", lambda: NOW+timedelta(seconds=1))
    with Session(engine) as db:
        selected = db.get(Service, service_id); selected.price_member = Decimal("9.87"); selected.price_passage = Decimal("12.34")
        db.add(GiftCardSettings(institute_id=institute, currency="CHF", updated_at=NOW, actor_id="configured")); db.commit()
        appointment = service.create_appointment(db, AppointmentCreate(institute_id=institute, employee_id=employee, service_id=service_id,
            customer_name="Fixture", start_time=NOW+timedelta(hours=3)), "manager")
        service.mark_appointment_no_show(db, appointment.id, "manager")
        reference = db.scalar(select(BookingEvent).where(BookingEvent.appointment_id == appointment.id, BookingEvent.event_type == "created"))
        closure = db.scalar(select(BookingEvent).where(BookingEvent.appointment_id == appointment.id, BookingEvent.event_type == "no_show"))
        request = values.Request(reference_event_id=reference.id, expected_fingerprint=reference.price_reference["fingerprint"],
            closure_event_id=closure.id, rate="member", reason="Explicit historical rate scenario")
        member = values.preview(db, institute, appointment.id, request, "signed-manager")
        passage = values.preview(db, institute, appointment.id, request.model_copy(update={"rate": "passage"}), "signed-manager")
        assert member.estimated_value.amount_minor == "987" and passage.estimated_value.amount_minor == "1234"
        assert member.estimated_value.currency == "CHF" and not member.retained and not member.causal_loss_proven
        selected.price_member = Decimal("99"); db.get(GiftCardSettings, institute).currency = "EUR"; db.commit()
        assert values.preview(db, institute, appointment.id, request, "signed-manager").estimated_value == member.estimated_value
        for change in ({"expected_fingerprint": "0"*64}, {"closure_event_id": reference.id}, {"reference_event_id": "foreign"}):
            with pytest.raises(HTTPException): values.preview(db, institute, appointment.id, request.model_copy(update=change), "signed-manager")
        with pytest.raises(HTTPException): values.preview(db, institute, appointment.id, request, "")
        # New snapshots retain uncertainty; no caller amount substitutes for it.
        for n, reason in enumerate(("missing_rate", "invalid_rate", "unknown_currency")):
            selected.price_member = None if reason == "missing_rate" else Decimal("-1") if reason == "invalid_rate" else Decimal("9.87")
            db.get(GiftCardSettings, institute).updated_at = NOW+timedelta(days=1) if reason == "unknown_currency" else NOW
            db.commit()
            additional = service.create_appointment(db, AppointmentCreate(institute_id=institute, employee_id=employee, service_id=service_id,
                customer_name="Fixture", start_time=NOW+timedelta(hours=6+n*3)), "manager")
            service.cancel_appointment(db, additional.id, "manager")
            added_reference = db.scalar(select(BookingEvent).where(BookingEvent.appointment_id == additional.id, BookingEvent.event_type == "created"))
            added_closure = db.scalar(select(BookingEvent).where(BookingEvent.appointment_id == additional.id, BookingEvent.event_type == "cancelled"))
            terms = values.Request(reference_event_id=added_reference.id, expected_fingerprint=added_reference.price_reference["fingerprint"],
                closure_event_id=added_closure.id, rate="member", reason="Explicit uncertainty fixture")
            unavailable = values.preview(db, institute, additional.id, terms, "signed-manager")
            assert unavailable.estimated_value is None and unavailable.unavailable_reason == reason
        return appointment.id, request


def test_sqlite_historical_rate_scenario_and_signed_preview(client, monkeypatch):
    institute, employee, service_id, _, _ = setup(client)
    appointment, request = exercise(main_module.engine, institute, employee, service_id, monkeypatch)
    path = f"/api/v1/revenue/institutes/{institute}/appointments/{appointment}/closure-value-preview"
    headers = _auth_headers("responsable_institut", institute)
    response = client.post(path, headers=headers, json=request.model_dump(mode="json"))
    assert response.status_code == 200 and response.json()["estimated_value"]["amount_minor"] == "987"
    assert response.json()["actor_id"] == "test-user"
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        assert client.post(path, headers=_auth_headers(role, owner), json=request.model_dump(mode="json")).status_code == 403
    assert client.post(path, json=request.model_dump(mode="json")).status_code == 403
    assert client.post(path, headers=headers, json={**request.model_dump(mode="json"), "amount_minor": "999"}).status_code == 422


def test_postgres_historical_rate_scenario(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)
