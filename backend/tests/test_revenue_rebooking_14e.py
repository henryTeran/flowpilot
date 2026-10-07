from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.revenue import rebooking
from app.modules.crm import event_sources, automation_originals
from app.modules.customers.models import Customer
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.planning.models import ServiceSession
from app.modules.appointments.models import Appointment
from test_revenue_billing_14a import NOW
from test_crm_automation_originals_12aa import body
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def exercise(engine, institute, employee, service, monkeypatch):
    monkeypatch.setattr(rebooking, "utcnow", lambda: NOW)
    monkeypatch.setattr(event_sources, "utcnow", lambda: NOW-timedelta(days=10))
    monkeypatch.setattr(automation_originals, "utcnow", lambda: NOW)
    with Session(engine) as db:
        for n in range(25):
            db.add(Customer(id=f"rebook-{n:02}", institute_id=institute, display_name="Fixture", phone=None,
                search_name="fixture", phone_digits="", idempotency_key=f"rebook-{n}", creation_fingerprint="0"*64,
                created_at=NOW-timedelta(days=3), created_by="manager"))
            db.add(QueueTicket(id=f"rebook-ticket-{n}", institute_id=institute, customer_id=f"rebook-{n:02}",
                ticket_number=f"R{n}", status="paid", arrival_time=NOW-timedelta(days=2), paid_at=NOW-timedelta(days=2)))
        db.flush()
        for n in range(25):
            db.add(TicketLine(id=f"rebook-line-{n}", ticket_id=f"rebook-ticket-{n}", service_id=service, quantity=1, duration_minutes=30))
        db.flush()
        for n in range(25):
            db.add(ServiceSession(id=f"rebook-care-{n}", institute_id=institute, employee_id=employee, service_id=service,
                ticket_line_id=f"rebook-line-{n}", start_time=NOW-timedelta(days=2, minutes=30),
                planned_end_time=NOW-timedelta(days=2), real_end_time=NOW-timedelta(days=2), duration_minutes=30, status="completed"))
        db.commit()
        absent = rebooking.read(db, institute)
        assert absent.page.total == 0 and absent.diagnostics["policy_absent"] == 25
        template = body(institute)
        rules = [{**r.model_dump(), "enabled": r.trigger == "rebooking", "offset_us": 1 if r.trigger == "rebooking" else r.offset_us}
            for r in template.policy.rules]
        original = automation_originals.create(db, institute, body(institute, rules=rules), "manager")
        first = rebooking.read(db, institute)
        last = rebooking.read(db, institute, 20)
        assert first.page.total == last.page.total == first.examined_customers == 25
        assert len(first.opportunities) == 20 and len(last.opportunities) == 5
        assert all(row.evidence.captured_at == row.candidate.captured_at == NOW and row.estimated_value is None
            and row.evidence.lifecycle_original is None and not row.action_executed for row in first.opportunities+last.opportunities)
        assert not first.delivery_authorized and not first.external_message_sent
        db.add(Appointment(id="rebook-existing", institute_id=institute, customer_id="rebook-00", customer_name="Fixture",
            employee_id=employee, service_id=service, start_time=NOW+timedelta(hours=1), end_time=NOW+timedelta(hours=2), status="scheduled"))
        db.commit()
        suppressed = rebooking.read(db, institute)
        assert suppressed.page.total == 24 and suppressed.already_booked_customers == 1
        assert all(row.candidate.customer_id != "rebook-00" for row in suppressed.opportunities)
        db.add(Appointment(id="rebook-malformed", institute_id=institute, customer_id="rebook-24", customer_name="Fixture",
            employee_id=employee, service_id=service, start_time=NOW+timedelta(hours=2), end_time=NOW+timedelta(hours=1), status="confirmed"))
        db.commit()
        with pytest.raises(HTTPException): rebooking.read(db, institute, limit=1)
        db.delete(db.get(Appointment, "rebook-malformed")); db.commit()
        db.get(ServiceSession, "rebook-care-24").real_end_time = None; db.commit()
        diagnostic = rebooking.read(db, institute, limit=1)
        assert diagnostic.page.total == 23 and diagnostic.diagnostics["care_invalid_actual_times"] == 1
        assert rebooking.read(db, institute, 23).opportunities == ()
        for offset, limit in ((-1,20), (0,51), (True,20)):
            with pytest.raises(HTTPException): rebooking.read(db, institute, offset, limit)
        for name in ("complete_customer_history", "delivery_authorized", "external_message_sent"):
            with pytest.raises(ValueError): rebooking.Rebooking.model_validate({**first.model_dump(), name: 0})
        disabled_rules = [{**r, "enabled": False} for r in rules]
        disabled_policy = automation_originals.create(db, institute, body(institute, "disabled-rebooking", original.id, rules=disabled_rules), "manager")
        disabled = rebooking.read(db, institute)
        assert disabled.page.total == 0 and disabled.disabled_customers == 24 and disabled.no_candidate_customers == 1
        future_rules = [{**r, "offset_us": 30*86400000000 if r["trigger"] == "rebooking" else r["offset_us"]} for r in rules]
        future_policy = automation_originals.create(db, institute, body(institute, "future-rebooking", disabled_policy.id, rules=future_rules), "manager")
        future = rebooking.read(db, institute)
        assert future.page.total == 0 and future.scheduled_customers == 24 and future.no_candidate_customers == 1
        automation_originals.create(db, institute, body(institute, "restore-rebooking", future_policy.id, rules=rules), "manager")


def test_sqlite_actual_rebooking_sources_and_signed_manager_catalog(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    exercise(main_module.engine, institute, employee, service, monkeypatch)
    path = f"/api/v1/revenue/institutes/{institute}/rebooking"
    headers = _auth_headers("responsable_institut", institute)
    response = client.get(path, headers=headers)
    assert response.status_code == 200 and response.json()["page"]["total"] == 23
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        assert client.get(path, headers=_auth_headers(role, owner)).status_code == 403
    assert client.get(path).status_code == 403
    assert client.get(path+"?limit=51", headers=headers).status_code == 422
    assert client.post(path, headers=headers).status_code == 405


def test_postgres_actual_rebooking_sources(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)
