from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.workforce import rebooking
from app.modules.workforce.absence_schemas import AbsenceCancel
from app.modules.appointments.models import Appointment
from app.modules.appointments.models import BookingEvent
from test_rebooking_sources_11t import exercise as seed
from test_postgres_scheduling_4d import postgres_flow
from test_workforce_absences_11b import setup

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
def payload(key="original"):
    return rebooking.RebookingCreate(source_kind="session", source_id="rebook-session", target_appointment_id="rebook-target", reason="Explicit link", idempotency_key=key)


def exercise(engine, institute, employee, service, monkeypatch):
    seed(engine, institute, employee, service)
    monkeypatch.setattr(rebooking, "utcnow", lambda: NOW)
    with Session(engine) as db:
        original = rebooking.create(db, institute, payload(), "signed")
        assert original.employee_id == employee and original.source_capture.customer_id == "rebook-customer"
        assert original.booking_capture.creation_event_id == "rebook-event"
        assert rebooking.create(db, institute, payload(), "signed") == original
        changed = payload().model_copy(update={"reason": "Other reason"})
        with pytest.raises(HTTPException): rebooking.create(db, institute, changed, "signed")
        db.rollback()
        # Target uniqueness also applies across the two execution kinds.
        changed = payload("other-source").model_copy(update={"source_kind": "appointment", "source_id": "rebook-original"})
        with pytest.raises(HTTPException): rebooking.create(db, institute, changed, "signed")
        db.rollback()
        target = db.get(Appointment, "rebook-target")
        alternative = Appointment(id="alternative", institute_id=institute, employee_id=employee, service_id=service,
            customer_name="Private", customer_id=target.customer_id, status="scheduled", start_time=target.start_time,
            end_time=target.end_time, booked_start_time=target.booked_start_time, booked_end_time=target.booked_end_time)
        db.add(alternative); db.flush()
        event = db.get(BookingEvent, "rebook-event")
        db.add(BookingEvent(id="alternative-event", institute_id=institute, appointment_id=alternative.id, event_type="created",
            occurred_at=event.occurred_at, after=event.after)); db.commit()
        changed = payload("other-target").model_copy(update={"target_appointment_id": alternative.id})
        with pytest.raises(HTTPException): rebooking.create(db, institute, changed, "signed")
        db.rollback()
        for body, actor in [(payload("another"), "signed"), (payload(), "another-actor")]:
            with pytest.raises(HTTPException): rebooking.create(db, institute, body, actor)
        # Roll back the locked transaction opened by the rejected write.
        db.rollback()
        target = db.get(Appointment, "rebook-target"); target.status = "cancelled"; target.customer_id = None; db.commit()
        monkeypatch.setattr(rebooking, "utcnow", lambda: datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert rebooking.create(db, institute, payload(), "signed") == original
        cancelled = rebooking.cancel(db, institute, original.id, AbsenceCancel(reason="Correction", idempotency_key="cancel"), "signed")
        assert rebooking.cancel(db, institute, original.id, AbsenceCancel(reason="Correction", idempotency_key="cancel"), "signed") == cancelled
        for reason, actor in [("Changed", "signed"), ("Correction", "other-actor")]:
            with pytest.raises(HTTPException): rebooking.cancel(db, institute, original.id, AbsenceCancel(reason=reason, idempotency_key="cancel"), actor)
            db.rollback()
        recovered = rebooking.original(db, institute, "original")
        assert recovered.cancellation == cancelled
        assert recovered.model_dump(exclude={"cancellation"}) == original.model_dump(exclude={"cancellation"})
        with pytest.raises(HTTPException): rebooking.cancel(db, institute, original.id, AbsenceCancel(reason="Correction", idempotency_key="second-cancel"), "signed")
        db.rollback()
        page = rebooking.list_records(db, institute, employee, 1, 0)
        assert page.page.total == 1 and page.rows == [recovered]
        assert rebooking.list_records(db, institute, employee, 1, 1).rows == []
        assert rebooking.original(db, "foreign", "original") is None
        assert rebooking.original(db, institute, "missing") is None
        # A corrected explicit attribution can reuse cancelled source/target,
        # while both original facts remain intact.
        target.status = "scheduled"; target.customer_id = "rebook-customer"; db.commit()
        monkeypatch.setattr(rebooking, "utcnow", lambda: NOW)
        corrected = rebooking.create(db, institute, payload("corrected"), "signed")
        assert corrected.id != original.id
        assert rebooking.list_records(db, institute, employee).page.total == 2


def test_sqlite_rebooking_original_replay_cancellation_and_http_scope(client, monkeypatch):
    institute, employee, service, path, headers = setup(client)
    exercise(main_module.engine, institute, employee, service, monkeypatch)
    assert client.get(path+"/rebookings/original/original", headers=headers).status_code == 200
    assert client.get(path+"/rebooking-cancellations/original/cancel", headers=headers).json()["actor_id"] == "signed"
    assert client.get(path+"/rebooking-cancellations/original/missing", headers=headers).json() is None
    assert client.get(path+f"/employees/{employee}/rebookings", headers=headers).json()["page"]["total"] == 2
    from test_ticket_workflow import _auth_headers
    for role, scope in [("accueil", institute), ("responsable_institut", "foreign")]:
        rejected = _auth_headers(role, scope)
        assert client.post(path+"/rebookings", headers=rejected, json=payload().model_dump()).status_code == 403
        assert client.get(path+"/rebookings/original/original", headers=rejected).status_code == 403
    assert client.get(path+f"/employees/{employee}/rebookings?limit=51", headers=headers).status_code == 422
    corrected = client.get(path+"/rebookings/original/corrected", headers=headers).json()
    correction = client.post(path+f"/rebookings/{corrected['id']}/cancel", headers=headers, json={"reason": "API fixture correction", "idempotency_key": "api-correct"})
    assert correction.status_code == 200, correction.text
    body = payload("api-original").model_dump()
    reply = client.post(path+"/rebookings", headers=headers, json=body)
    assert reply.status_code == 200, reply.text
    original = reply.json(); assert original["actor_id"] == "test-user"
    assert client.post(path+"/rebookings", headers=headers, json=body).json() == original
    assert client.get(path+f"/rebookings/{original['id']}", headers=headers).json() == original
    terms = {"reason": "Separate API cancellation", "idempotency_key": "api-cancel"}
    cancelled = client.post(path+f"/rebookings/{original['id']}/cancel", headers=headers, json=terms)
    assert cancelled.status_code == 200, cancelled.text
    assert client.post(path+f"/rebookings/{original['id']}/cancel", headers=headers, json=terms).json() == cancelled.json()
    assert client.get(path+"/rebooking-cancellations/original/api-cancel", headers=headers).json() == cancelled.json()


def test_actual_postgres_rebooking_originals_and_competing_attribution(postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    exercise(engine, institute, employee, service, monkeypatch)
    with Session(engine) as db:
        row = rebooking.original(db, institute, "corrected")
        rebooking.cancel(db, institute, row.id, AbsenceCancel(reason="Race fixture", idempotency_key="race-cancel"), "signed")
    barrier = Barrier(2)
    def writer(key):
        with Session(engine) as db:
            barrier.wait()
            try: return rebooking.create(db, institute, payload(key), "signed").id
            except HTTPException: db.rollback(); return None
    with ThreadPoolExecutor(2) as pool:
        winners = list(pool.map(writer, ["race-one", "race-two"]))
    assert len([v for v in winners if v]) == 1
    with Session(engine) as db:
        assert rebooking.list_records(db, institute, employee).page.total == 3
        rebooking.cancel(db, institute, next(v for v in winners if v), AbsenceCancel(reason="Shared replay race", idempotency_key="shared-race-cancel"), "signed")
    barrier = Barrier(2)
    with ThreadPoolExecutor(2) as pool:
        replays = list(pool.map(writer, ["shared-key", "shared-key"]))
    assert replays[0] is not None and replays[0] == replays[1]
