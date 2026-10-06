from datetime import timedelta
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError
import pytest
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.appointments.models import Appointment, AppointmentInvoiceLine
from app.modules.appointments.service import start_appointment, complete_appointment
from app.modules.inventory.models import StockServiceBasis
from app.modules.inventory import worklist
from app.modules.tickets.service import add_checkout_ticket_line, remove_checkout_ticket_line
from app.shared.time import utcnow
from test_ticket_workflow import _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow


def exercise(engine, institute, employee, service):
    with Session(engine) as db:
        now = utcnow()
        db.add(Appointment(id="provenance-booking", institute_id=institute, employee_id=employee,
            service_id=service, customer_name="Private", start_time=now,
            end_time=now + timedelta(minutes=15), status="arrived"))
        db.commit()
        start_appointment(db, "provenance-booking", "signed")
        basis = db.scalar(select(StockServiceBasis).where(StockServiceBasis.appointment_id == "provenance-booking"))
        assert worklist.detail(db, institute, basis.id).billing_state == "not_issued"
        complete_appointment(db, "provenance-booking", "signed")
        fact = db.get(AppointmentInvoiceLine, "provenance-booking")
        original = (fact.ticket_id, fact.ticket_line_id, fact.actor_id, fact.occurred_at)
        assert fact.actor_id == "signed"
        assert worklist.detail(db, institute, basis.id).billing_state == "active"
        add_checkout_ticket_line(db, fact.ticket_id, service)
        remove_checkout_ticket_line(db, fact.ticket_id, fact.ticket_line_id, "signed")
        detail = worklist.detail(db, institute, basis.id)
        assert detail.billing_state == "removed" and detail.invoice_removed_at is not None
        assert detail.consumption is None and detail.quantity == 1
        assert detail.ticket_number is not None
        complete_appointment(db, "provenance-booking", "different-replay")
        db.refresh(fact)
        assert (fact.ticket_id, fact.ticket_line_id, fact.actor_id, fact.occurred_at) == original
        assert db.scalar(select(func.count()).select_from(AppointmentInvoiceLine)) == 1
        if engine.dialect.name == "postgresql":
            for field, constraint in (("appointment_id", "fk_appointment_invoice_source_owner"),
                    ("ticket_id", "fk_appointment_invoice_ticket_owner"),
                    ("ticket_line_id", "fk_appointment_invoice_line_owner")):
                with pytest.raises(IntegrityError, match=constraint):
                    with db.begin_nested():
                        db.execute(text(f"UPDATE appointment_invoice_lines SET {field}='foreign-missing' WHERE appointment_id='provenance-booking'"))
        # Simulate a historical completed booking whose invoice header is known,
        # but whose exact original line was never captured. No guessing/backfill.
        db.delete(fact)
        db.commit()
        complete_appointment(db, "provenance-booking", "signed")
        unknown = worklist.detail(db, institute, basis.id)
        assert unknown.billing_state == "unknown"
        assert unknown.ticket_number is None and unknown.invoice_removed_at is None
        assert db.get(AppointmentInvoiceLine, "provenance-booking") is None


def test_appointment_invoice_original_line_and_legacy_unknown(client):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise(main_module.engine, institute, employees[0]["id"], services[0]["id"])


def test_postgres_appointment_invoice_original_line_and_legacy_unknown(postgres_flow):
    engine, institute, employee, service = postgres_flow
    exercise(engine, institute, employee, service)
