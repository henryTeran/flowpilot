from datetime import timedelta
from decimal import Decimal
import copy
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import pytest
import app.main as main_module
from app.modules.appointments import service, events, price_references
from app.modules.appointments.models import BookingEvent, Appointment
from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.modules.services.models import Service
from app.modules.gift_cards.models import GiftCardSettings
from test_revenue_billing_14a import NOW
from test_workforce_absences_11b import setup
from test_postgres_scheduling_4d import postgres_flow


def exercise(engine, institute, employee, service_id, monkeypatch):
    monkeypatch.setattr(service, "utcnow", lambda: NOW)
    monkeypatch.setattr(events, "utcnow", lambda: NOW)
    with Session(engine) as db:
        selected = db.get(Service, service_id)
        selected.price_passage = Decimal("12.34"); selected.price_member = Decimal("9.87")
        db.add(GiftCardSettings(institute_id=institute, currency="CHF", actor_id="configured", updated_at=NOW))
        db.commit()
        payload = AppointmentCreate(institute_id=institute, employee_id=employee, service_id=service_id,
            customer_name="Fixture", start_time=NOW+timedelta(hours=3), idempotency_key="price-reference-booking")
        appointment = service.create_appointment(db, payload, "signed-manager")
        original = db.scalar(select(BookingEvent).where(BookingEvent.appointment_id == appointment.id, BookingEvent.event_type == "created"))
        retained = copy.deepcopy(original.price_reference)
        assert retained["fingerprint"] == price_references.fingerprint(retained["terms"])
        terms = retained["terms"]
        assert terms["event_id"] == original.id and terms["actor_id"] == "signed-manager"
        assert terms["member_minor"] == "987" and terms["passage_minor"] == "1234" and terms["currency"] == "CHF"
        assert not terms["agreed_quote"] and not terms["paid_price"]
        selected.price_passage = Decimal("99.99"); db.get(GiftCardSettings, institute).currency = "EUR"; db.commit()
        assert service.create_appointment(db, payload, "retry-actor").id == appointment.id
        assert db.scalar(select(func.count()).select_from(BookingEvent).where(BookingEvent.appointment_id == appointment.id)) == 1
        service.update_appointment(db, appointment.id, AppointmentUpdate(notes="Note only"), "signed-manager")
        modified = db.scalar(select(BookingEvent).where(BookingEvent.appointment_id == appointment.id, BookingEvent.event_type == "modified"))
        assert modified.price_reference is None
        alternate = db.scalar(select(Service).where(Service.id != service_id))
        alternate.price_member = None; alternate.price_passage = Decimal("4.56"); db.commit()
        service.update_appointment(db, appointment.id, AppointmentUpdate(service_id=alternate.id), "signed-manager")
        references = db.scalars(select(BookingEvent).where(BookingEvent.appointment_id == appointment.id, BookingEvent.price_reference.is_not(None))).all()
        assert len(references) == 2
        changed = next(row for row in references if row.id != original.id)
        assert changed.price_reference["terms"]["service_id"] == alternate.id
        assert changed.price_reference["terms"]["member_quality"] == "missing" and changed.price_reference["terms"]["passage_minor"] == "456"
        assert changed.price_reference["terms"]["currency"] == "EUR"
        db.refresh(original)
        assert original.price_reference == retained
        service.cancel_appointment(db, appointment.id, "signed-manager")
        closure = db.scalar(select(BookingEvent).where(BookingEvent.appointment_id == appointment.id, BookingEvent.event_type == "cancelled"))
        assert closure.price_reference is None  # no reprice at cancellation
        db.get(GiftCardSettings, institute).updated_at = NOW+timedelta(days=1); db.commit()
        next_payload = payload.model_copy(update={"start_time": NOW+timedelta(hours=6), "idempotency_key": "future-currency-reference"})
        next_booking = service.create_appointment(db, next_payload, "signed-manager")
        next_event = db.scalar(select(BookingEvent).where(BookingEvent.appointment_id == next_booking.id, BookingEvent.event_type == "created"))
        assert next_event.price_reference["terms"]["currency"] is None
        assert next_event.price_reference["terms"]["currency_unavailable_reason"] == "future_settings"
        before_count = db.scalar(select(func.count()).select_from(BookingEvent))
        original_save = service.save_appointment
        def failed_save(db, appointment):
            db.flush()
            raise RuntimeError("Owned booking commit failure")
        monkeypatch.setattr(service, "save_appointment", failed_save)
        failed_payload = payload.model_copy(update={"start_time": NOW+timedelta(hours=10), "idempotency_key": "rollback-price-reference"})
        with pytest.raises(RuntimeError): service.create_appointment(db, failed_payload, "signed-manager")
        db.rollback(); monkeypatch.setattr(service, "save_appointment", original_save)
        assert db.scalar(select(func.count()).select_from(Appointment).where(Appointment.idempotency_key == "rollback-price-reference")) == 0
        assert db.scalar(select(func.count()).select_from(BookingEvent)) == before_count


def test_sqlite_booking_replay_and_service_selection_references(client, monkeypatch):
    institute, employee, service_id, _, _ = setup(client)
    exercise(main_module.engine, institute, employee, service_id, monkeypatch)


def test_postgres_booking_replay_and_service_selection_references(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)
