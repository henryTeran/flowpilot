from copy import deepcopy
from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.revenue import closure_valuation_originals as originals, booking_valuation as values
from app.modules.revenue.models import ClosureValuationOriginal as Row
from test_revenue_booking_valuation_14j import exercise
from test_revenue_billing_14a import NOW
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def check(engine, institute, employee, service, monkeypatch):
    appointment, request = exercise(engine, institute, employee, service, monkeypatch)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW+timedelta(seconds=1))
    declaration = originals.Declaration(valuation=request, idempotency_key="retained-member")
    with Session(engine) as db:
        result = originals.create(db, institute, appointment, declaration, "signed-manager")
        assert result.original["estimated_value"] == dict(currency="CHF", amount_minor="987", basis="explicit_historical_catalog_rate_scenario")
        assert result.original["retained"] is True and result.original["causal_loss_proven"] is False and result.original["action_executed"] is False
        assert originals.require(db, institute, result.original["id"]) == result
        assert originals.by_key(db, institute, declaration.idempotency_key) == result
        assert originals.by_key(db, institute, "absent") is None
        for change in (dict(actor="another"), dict(appointment="foreign"), dict(payload=declaration.model_copy(update={"valuation": request.model_copy(update={"rate": "passage"})}))):
            args = dict(db=db, institute=institute, appointment=appointment, payload=declaration, actor="signed-manager"); args.update(change)
            with pytest.raises(HTTPException): originals.create(**args)
        # Independent variants of one closure remain separate; no causal sum.
        for n in range(24):
            variant = request.model_copy(update={"rate": "passage" if n == 0 else "member", "reason": "Scénario 😀\n2026-10-07T12:00:00Z"})
            row = originals.create(db, institute, appointment, declaration.model_copy(update={"idempotency_key": f"variant-{n:02}", "valuation": variant}), "signed-manager")
            assert row.original["estimated_value"]["amount_minor"] == ("1234" if n == 0 else "987")
        first = originals.audit(db, institute); last = originals.audit(db, institute, 20)
        assert first.total == last.total == 25 and len(first.originals) == 20 and len(last.originals) == 5
        assert first.full_original_cohort_verified and not first.causal_loss_proven
    old_preview = values.preview
    monkeypatch.setattr(values, "preview", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Replay recaptured current sources")))
    monkeypatch.setattr(originals, "utcnow", lambda: NOW+timedelta(days=100))
    with Session(engine) as db:
        assert originals.create(db, institute, appointment, declaration, "signed-manager") == result
        assert originals.require(db, institute, result.original["id"]) == result
    monkeypatch.setattr(values, "preview", old_preview)
    with Session(engine) as db:
        row = db.scalar(select(Row).where(Row.id == last.originals[-1].original["id"]))
        good = deepcopy(row.original)
        for mutate in (
            lambda o: o["estimated_value"].update(amount_minor="999"),
            lambda o: o.update(actor_id="another"), lambda o: o.update(retained=1),
            lambda o: o["reference_event"].update(institute_id="foreign"),
            lambda o: o["reference_event"]["after"].update(service_id="foreign"),
            lambda o: o["evidence"]["before"].update(status="cancelled"),
            lambda o: o["request"].update(expected_fingerprint="0"*64),
            lambda o: o.update(causal_loss_proven=True),
        ):
            bad = deepcopy(good); mutate(bad); row.original = bad; row.fingerprint = originals.fingerprint(bad); db.commit()
            with pytest.raises(HTTPException): originals.audit(db, institute, 0, 20)  # Bad original is off page.
            row.original = deepcopy(good); row.fingerprint = originals.fingerprint(good); db.commit()
        # Flush failure rolls back; lost commit acknowledgement is recovered by key.
        actual_flush = db.flush
        def failed_flush(*args, **kwargs):
            if any(isinstance(pending, Row) for pending in db.new):
                raise RuntimeError("forced flush failure")
            return actual_flush(*args, **kwargs)
        with monkeypatch.context() as patch:
            patch.setattr(db, "flush", failed_flush)
            with pytest.raises(RuntimeError): originals.create(db, institute, appointment, declaration.model_copy(update={"idempotency_key": "failed"}), "signed-manager")
        assert originals.by_key(db, institute, "failed") is None
        commit = db.commit
        def lost():
            commit(); raise RuntimeError("lost acknowledgement")
        with monkeypatch.context() as patch:
            patch.setattr(db, "commit", lost)
            with pytest.raises(RuntimeError): originals.create(db, institute, appointment, declaration.model_copy(update={"idempotency_key": "lost"}), "signed-manager")
        recovered = originals.by_key(db, institute, "lost")
        assert recovered is not None and originals.create(db, institute, appointment, declaration.model_copy(update={"idempotency_key": "lost"}), "signed-manager") == recovered
        assert db.scalar(select(func.count()).select_from(Row)) == 26
        for bounds in ((-1, 20), (0, 51), (True, 20)):
            with pytest.raises(HTTPException): originals.audit(db, institute, *bounds)
        from app.modules.appointments.models import BookingEvent
        for closure in db.scalars(select(BookingEvent).where(BookingEvent.institute_id == institute, BookingEvent.event_type == "cancelled")):
            reference = db.scalar(select(BookingEvent).where(BookingEvent.appointment_id == closure.appointment_id, BookingEvent.event_type == "created"))
            uncertain = originals.Declaration(valuation=values.Request(reference_event_id=reference.id, expected_fingerprint=reference.price_reference["fingerprint"],
                closure_event_id=closure.id, rate="member", reason="Retain explicit uncertainty"), idempotency_key="uncertain-"+closure.id)
            retained = originals.create(db, institute, closure.appointment_id, uncertain, "signed-manager")
            assert retained.original["estimated_value"] is None and retained.original["unavailable_reason"] in {"missing_rate", "invalid_rate", "unknown_currency"}
            assert originals.by_key(db, institute, uncertain.idempotency_key) == retained
        from app.modules.appointments import service as bookings
        from app.modules.appointments.schemas import AppointmentCreate
        from app.modules.services.models import Service
        from app.modules.gift_cards.models import GiftCardSettings
        from decimal import Decimal
        db.get(Service, service).price_member = Decimal("0")
        settings = db.get(GiftCardSettings, institute); settings.currency = "CHF"; settings.updated_at = NOW; db.commit()
        zero = bookings.create_appointment(db, AppointmentCreate(institute_id=institute, employee_id=employee, service_id=service,
            customer_name="Known-zero fixture", start_time=NOW+timedelta(days=2)), "manager")
        bookings.cancel_appointment(db, zero.id, "manager")
        reference = db.scalar(select(BookingEvent).where(BookingEvent.appointment_id == zero.id, BookingEvent.event_type == "created"))
        closure = db.scalar(select(BookingEvent).where(BookingEvent.appointment_id == zero.id, BookingEvent.event_type == "cancelled"))
        zero_terms = originals.Declaration(valuation=values.Request(reference_event_id=reference.id, expected_fingerprint=reference.price_reference["fingerprint"], closure_event_id=closure.id,
            rate="member", reason="Retain explicit known zero"), idempotency_key="known-zero")
        valued_zero = originals.create(db, institute, zero.id, zero_terms, "signed-manager")
        assert valued_zero.original["estimated_value"]["amount_minor"] == "0" and valued_zero.original["unavailable_reason"] is None
        assert db.scalar(select(func.count()).select_from(Row)) == 30
        from app.modules.employees.models import Employee
        from app.modules.institutes.models import Institute
        owner = db.get(Institute, institute)
        db.add(Institute(id="valuation-foreign", region_id=owner.region_id, name="Foreign fixture", city="Fixture")); db.commit()
        staff = db.get(Employee, employee); staff.institute_id = "valuation-foreign"; db.commit()
        with pytest.raises(HTTPException): values.preview(db, institute, appointment, request, "signed-manager")
        with pytest.raises(HTTPException): originals.create(db, institute, appointment, declaration.model_copy(update={"idempotency_key": "foreign-staff"}), "signed-manager")
        assert originals.create(db, institute, appointment, declaration, "signed-manager") == result
        assert originals.by_key(db, institute, "foreign-staff") is None
        staff.institute_id = institute; db.commit()
    return appointment, declaration


def test_sqlite_retained_closure_decisions_routes_and_sources(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    appointment, declaration = check(main_module.engine, institute, employee, service, monkeypatch)
    root = f"/api/v1/revenue/institutes/{institute}"
    path = root+f"/appointments/{appointment}/closure-value-originals"
    headers = _auth_headers("responsable_institut", institute)
    response = client.post(path, headers=headers, json={**declaration.model_dump(mode="json"), "idempotency_key": "api"})
    assert response.status_code == 200 and response.json()["original"]["actor_id"] == "test-user"
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        foreign = _auth_headers(role, owner)
        assert client.post(path, headers=foreign, json=declaration.model_dump(mode="json")).status_code == 403
        assert client.get(root+"/closure-value-originals", headers=foreign).status_code == 403
    assert client.post(path, json=declaration.model_dump(mode="json")).status_code == 403
    for field in ("actor_id", "amount_minor", "evidence"):
        assert client.post(path, headers=headers, json={**declaration.model_dump(mode="json"), field: "injected"}).status_code == 422
    identifier = response.json()["original"]["id"]
    assert client.get(root+f"/closure-value-originals/{identifier}", headers=headers).json() == response.json()
    assert client.get(root+"/closure-value-original-by-key?key=api", headers=headers).json() == response.json()
    assert client.get(root+"/closure-value-originals?offset=20&limit=20", headers=headers).json()["total"] == 31


def test_postgres_retained_closure_decisions(postgres_flow, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    appointment, declaration = check(*postgres_flow, monkeypatch)
    engine, institute, _, _ = postgres_flow
    barrier = Barrier(2)
    def retain():
        with Session(engine) as db:
            barrier.wait(timeout=10)
            return originals.create(db, institute, appointment, declaration.model_copy(update={"idempotency_key": "race"}), "signed-manager")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(retain) for _ in range(2)]
        a, b = [future.result(timeout=30) for future in futures]
    assert a == b
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Row).where(Row.idempotency_key == "race")) == 1
