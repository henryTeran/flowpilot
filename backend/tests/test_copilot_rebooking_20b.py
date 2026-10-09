from datetime import timedelta
import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.copilot import customer
from app.modules.crm import automation_originals, rebooking
from app.modules.customers.models import Customer
from app.modules.appointments.models import Appointment
from app.modules.planning.models import ServiceSession
from app.modules.waitlist.originals import fingerprint
from test_crm_return_sources_12k import sources
from test_crm_billing_12b import NOW
from test_crm_automation_originals_12aa import body as policy_body
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data
from test_copilot_customer_20a import post

MESSAGE = "Examiner les opportunites de reprise rendez-vous"


def exercise(client, engine, institute, employee, service, monkeypatch):
    monkeypatch.setattr(customer, "utcnow", lambda: NOW)
    monkeypatch.setattr(automation_originals, "utcnow", lambda: NOW)
    with Session(engine) as db:
        sources(db, institute, employee, service)
        db.get(Customer, "customer_crm").created_at = NOW - timedelta(days=2)
        db.commit()
    def query(identifier="customer_crm", role="responsable_institut"):
        return post(client, institute, identifier, MESSAGE, role)
    assert query(role="accueil").status_code == 403
    assert query("customer_foreign").status_code == 404
    assert query(None).json()["status"] == "clarification"
    absent = query().json()["evidence"]["result"]
    assert absent["review"] == "unavailable" and absent["diagnostics"]["policy_absent"] == 1
    terms = policy_body(institute).policy.model_dump()["rules"]
    def rules(enabled=True, delay=1):
        return [{**r, "enabled": enabled if r["trigger"] == "rebooking" else False,
                 "offset_us": delay if r["trigger"] == "rebooking" else r["offset_us"]} for r in terms]
    with Session(engine) as db:
        original = automation_originals.create(db, institute, policy_body(institute, rules=rules()), "manager")
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", collect)
    try:
        response = query()
        assert response.status_code == 200, response.text
        value = response.json()
        evidence = value["evidence"]
        result = evidence["result"]
        assert value["capability"] == "CLIENT_REBOOKING_OPPORTUNITIES" and value["actions"] == []
        assert result["review"] == "available" and result["candidate"]["source"]["source_id"] == "eur"
        assert result["candidate"]["rule"]["trigger"] == "rebooking" and result["candidate"]["state"] == "due"
        assert result["policy_original_digest"] == fingerprint(original.model_dump(mode="json"))
        assert evidence["fingerprint"] == fingerprint({k: v for k, v in evidence.items() if k != "fingerprint"})
        assert not result["delivery_authorized"] and not result["execution_authorized"]
        assert all(field not in response.text for field in ('"communications"', '"birthday"', '"phone"', '"reason"', '"actor_id"'))
    finally:
        event.remove(engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}
    with Session(engine) as db:
        db.add(Appointment(id="rebooking_future", institute_id=institute, customer_id="customer_crm",
            customer_name="Private", employee_id=employee, service_id=service, phone="Secret",
            status="confirmed", start_time=NOW+timedelta(days=1), end_time=NOW+timedelta(days=1, minutes=30)))
        db.commit()
    booked = query().json()["evidence"]["result"]
    assert booked["review"] == "already_booked" and booked["active_bookings"][0]["appointment_id"] == "rebooking_future"
    with Session(engine) as db:
        db.get(Appointment, "rebooking_future").status = "cancelled"
        disabled = automation_originals.create(db, institute, policy_body(institute, "disabled", original.id, rules=rules(False)), "manager")
    assert query().json()["evidence"]["result"]["review"] == "disabled"
    with Session(engine) as db:
        delayed = automation_originals.create(db, institute, policy_body(institute, "delayed", disabled.id, rules=rules(delay=86400000000)), "manager")
    assert query().json()["evidence"]["result"]["review"] == "not_due"
    with Session(engine) as db:
        automation_originals.create(db, institute, policy_body(institute, "restored", delayed.id, rules=rules()), "manager")
        db.get(ServiceSession, "care_0").real_end_time = None
        db.commit()
    damaged = query().json()["evidence"]["result"]
    assert damaged["review"] == "unavailable" and damaged["candidate"] is None
    assert damaged["diagnostics"]["care_invalid_actual_times"] == 1
    with Session(engine) as db:
        db.get(ServiceSession, "care_0").real_end_time = NOW-timedelta(hours=6)+timedelta(minutes=1)
        db.get(Appointment, "rebooking_future").status = "confirmed"
        db.get(Appointment, "rebooking_future").start_time = NOW+timedelta(days=2)
        db.commit()
    malformed = query().json()["evidence"]["result"]
    assert malformed["review"] == "unavailable" and malformed["invalid_booking_count"] == 1


def test_sqlite_signed_rebooking_sources_and_unknowns(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise(client, main_module.engine, institute, employees[0]["id"], services[0]["id"], monkeypatch)


def test_postgres_signed_rebooking_sources_and_unknowns(client, postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, engine, institute, employee, service, monkeypatch)
