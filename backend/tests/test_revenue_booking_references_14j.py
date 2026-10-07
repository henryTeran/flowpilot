import copy
from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.revenue import booking_references as refs
from app.modules.appointments.models import BookingEvent
from app.modules.appointments import service, events, price_references
from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.modules.services.models import Service
from test_revenue_billing_14a import NOW
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def exercise(engine, institute, employee, service_id, monkeypatch):
    for module in (refs, service, events): monkeypatch.setattr(module, "utcnow", lambda: NOW)
    with Session(engine) as db:
        alternative = db.scalar(select(Service).where(Service.id != service_id)).id
        appointment = service.create_appointment(db, AppointmentCreate(institute_id=institute, employee_id=employee,
            service_id=service_id, customer_name="Fixture", start_time=NOW+timedelta(hours=3), idempotency_key="reference-pages"), "signed-manager")
        for n in range(24):
            service.update_appointment(db, appointment.id, AppointmentUpdate(service_id=alternative if n % 2 == 0 else service_id), "signed-manager")
        first, last = refs.read(db, institute, appointment.id), refs.read(db, institute, appointment.id, 20)
        assert first.page.total == last.page.total == 25 and len(first.originals) == 20 and len(last.originals) == 5
        assert first.legacy_service_selection_events == 0
        assert all(price_references.fingerprint(original.terms) == original.fingerprint for original in first.originals+last.originals)
        assert all(original.terms["currency"] is None and original.terms["currency_unavailable_reason"] == "settings_absent" for original in first.originals)
        # Choose a guaranteed off-page source regardless of equal-clock ID order.
        event = db.get(BookingEvent, last.originals[-1].terms["event_id"])
        valid = copy.deepcopy(event.price_reference)
        bad = copy.deepcopy(valid); bad["terms"]["passage_minor"] = "99999"
        event.price_reference = bad; db.commit()
        with pytest.raises(HTTPException): refs.read(db, institute, appointment.id, limit=1)
        for update in ({"event_id": "foreign"}, {"agreed_quote": 0}, {"currency": "CHF"}, {"actor_id": "different"}):
            bad = copy.deepcopy(valid); bad["terms"].update(update); bad["fingerprint"] = price_references.fingerprint(bad["terms"])
            event.price_reference = bad; db.commit()
            with pytest.raises(HTTPException): refs.read(db, institute, appointment.id)
        event.price_reference = valid; db.commit()
        db.get(Service, service_id).price_passage = 999; db.commit()
        assert refs.read(db, institute, appointment.id).originals == first.originals
        assert refs.read(db, institute, appointment.id, 25).originals == ()
        service.cancel_appointment(db, appointment.id, "signed-manager")
        assert refs.read(db, institute, appointment.id).originals == first.originals
        # A legacy missing snapshot is visible as coverage, not today's price.
        event.price_reference = None; db.commit()
        legacy = refs.read(db, institute, appointment.id)
        assert legacy.page.total == 24 and legacy.legacy_service_selection_events == 1
        for offset, limit in ((-1,20), (0,51), (True,20)):
            with pytest.raises(HTTPException): refs.read(db, institute, appointment.id, offset, limit)
        with pytest.raises(HTTPException): refs.read(db, institute, "foreign")
        return appointment.id


def test_sqlite_complete_reference_proof_and_signed_scope(client, monkeypatch):
    institute, employee, service_id, _, _ = setup(client)
    appointment = exercise(main_module.engine, institute, employee, service_id, monkeypatch)
    path = f"/api/v1/revenue/institutes/{institute}/appointments/{appointment}/price-references"
    headers = _auth_headers("responsable_institut", institute)
    response = client.get(path, headers=headers)
    assert response.status_code == 200 and response.json()["page"]["total"] == 24
    for original in response.json()["originals"]:
        assert price_references.fingerprint(original["terms"]) == original["fingerprint"]
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        assert client.get(path, headers=_auth_headers(role, owner)).status_code == 403
    assert client.get(path).status_code == 403
    assert client.get(path+"?limit=51", headers=headers).status_code == 422
    assert client.post(path, headers=headers).status_code == 405


def test_postgres_complete_reference_proof(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)
