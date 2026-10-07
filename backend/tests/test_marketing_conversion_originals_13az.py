from datetime import timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi import HTTPException
from sqlalchemy import event, select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import conversion_originals as service
from app.modules.marketing import conversion_sources
from app.modules.marketing.models import ConversionOriginal, ConversionHead
from app.modules.tickets.models import QueueTicket
from test_marketing_conversion_sources_13ax import exercise as prepare
from test_crm_billing_12b import NOW
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


def setup(engine, institute, monkeypatch):
    selection = prepare(engine, institute, monkeypatch)
    monkeypatch.setattr(service, "utcnow", lambda: NOW + timedelta(days=3))
    return service.Request(action="linked", ticket_id=selection.ticket_id, expected_previous_id=None,
        selection=selection, reason=selection.reason, idempotency_key=selection.idempotency_key)


def exercise(engine, institute, monkeypatch):
    payload = setup(engine, institute, monkeypatch)
    with Session(engine) as db:
        def fail(session, context, instances):
            if any(isinstance(row, ConversionHead) for row in session.new): raise RuntimeError("Injected head failure")
        event.listen(db, "before_flush", fail)
        try:
            with pytest.raises(RuntimeError): service.execute(db, institute, payload, "manager")
        finally: event.remove(db, "before_flush", fail)
        assert service.original(db, institute, payload.idempotency_key) is None and service.current(db, institute, payload.ticket_id) is None
        first = service.execute(db, institute, payload, "manager")
        assert service.current(db, institute, payload.ticket_id) == service.require(db, institute, first.id) == first
        assert first.attribution_fingerprint == service.fingerprint(first.attribution)
        db.get(QueueTicket, payload.ticket_id).total_amount = Decimal("43.21"); db.commit()
        monkeypatch.setattr(service, "utcnow", lambda: (_ for _ in ()).throw(AssertionError("Historical replay must precede current clock")))
        monkeypatch.setattr(conversion_sources, "utcnow", lambda: (_ for _ in ()).throw(AssertionError("Historical replay must not recapture billing")))
        assert service.execute(db, institute, payload, "manager") == first
        assert first.attribution.ticket.amount_minor == "12345"
        for actor, changed in [("other", payload), ("manager", payload.model_copy(update={"reason": "Changed reason", "selection": payload.selection.model_copy(update={"reason": "Changed reason"})}))]:
            with pytest.raises(HTTPException): service.execute(db, institute, changed, actor)
        monkeypatch.setattr(service, "utcnow", lambda: NOW + timedelta(days=3))
        monkeypatch.setattr(conversion_sources, "utcnow", lambda: NOW + timedelta(days=3))
        retract = service.Request(action="retracted", ticket_id=payload.ticket_id, expected_previous_id=first.id,
            selection=None, reason="Explicit mistaken attribution retracted", idempotency_key="retraction-key")
        second = service.execute(db, institute, retract, "manager")
        assert second.attribution == first.attribution and second.request.action == "retracted"
        assert service.execute(db, institute, payload, "manager") == first
        assert service.execute(db, institute, retract, "manager") == second
        with pytest.raises(HTTPException): service.execute(db, institute, retract.model_copy(update={"idempotency_key": "repeat-retraction"}), "manager")
        with pytest.raises(HTTPException): service.execute(db, institute, payload.model_copy(update={"idempotency_key": "stale", "selection": payload.selection.model_copy(update={"idempotency_key": "stale"})}), "manager")
        selection = payload.selection.model_copy(update={"idempotency_key": "corrected"})
        corrected = payload.model_copy(update={"expected_previous_id": second.id, "idempotency_key": "corrected", "selection": selection})
        third = service.execute(db, institute, corrected, "manager")
        assert third.attribution.ticket.amount_minor == "4321" and service.require(db, institute, first.id) == first
        page = service.audit(db, institute, payload.ticket_id)
        assert page.total == 3 and {o.id for o in page.items} == {first.id, second.id, third.id}
        row = db.get(ConversionOriginal, first.id); saved = row.attribution_fingerprint
        row.attribution_fingerprint = "0" * 64; db.commit()
        with pytest.raises(HTTPException): service.current(db, institute, payload.ticket_id)
        with pytest.raises(HTTPException): service.audit(db, institute, payload.ticket_id)
        row.attribution_fingerprint = saved; db.commit()
        assert service.current(db, institute, payload.ticket_id) == third
        pointer = db.get(ConversionHead, (institute, payload.ticket_id)); db.delete(pointer); db.commit()
        with pytest.raises(HTTPException): service.execute(db, institute, corrected.model_copy(update={"idempotency_key": "orphan", "expected_previous_id": None,
            "selection": corrected.selection.model_copy(update={"idempotency_key": "orphan"})}), "manager")
        assert db.scalar(select(func.count()).select_from(ConversionOriginal)) == 3
        db.add(ConversionHead(institute_id=institute, ticket_id=payload.ticket_id, original_id=third.id)); db.commit()
    return payload, first


def test_sqlite_conversion_originals_atomic_replay_retraction_and_signed_routes(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client); payload, first = exercise(main_module.engine, institute, monkeypatch)
    base = f"/api/v1/marketing/institutes/{institute}/conversions"
    headers = _auth_headers("responsable_institut", institute)
    for suffix in [f"/{first.id}", f"/original/{payload.idempotency_key}", f"/tickets/{payload.ticket_id}/current", f"/tickets/{payload.ticket_id}/audit"]:
        assert client.get(base + suffix, headers=headers).status_code == 200
        assert client.get(base + suffix, headers=_auth_headers("accueil", institute)).status_code == 403
        assert client.get(base + suffix, headers=_auth_headers("responsable_institut", "foreign")).status_code == 403
        assert client.get(base + suffix).status_code == 403
    assert client.post(base, headers=_auth_headers("accueil", institute), json=payload.model_dump(mode="json")).status_code == 403
    # Other actor cannot claim manager's existing protected request.
    assert client.post(base, headers=headers, json=payload.model_dump(mode="json")).status_code == 400
    with Session(main_module.engine) as db:
        db.add(QueueTicket(id="api-paid", institute_id=institute, customer_id="aud_000", ticket_number="api-paid",
            status="paid", arrival_time=NOW, paid_at=NOW + timedelta(days=1), currency="CHF", total_amount=Decimal("1"))); db.commit()
    selection = payload.selection.model_copy(update={"ticket_id": "api-paid", "idempotency_key": "api-link"})
    request = payload.model_copy(update={"ticket_id": "api-paid", "idempotency_key": "api-link", "selection": selection})
    linked = client.post(base, headers=headers, json=request.model_dump(mode="json"))
    assert linked.status_code == 200 and linked.json()["actor_id"] == "test-user"
    assert client.post(base, headers=headers, json=request.model_dump(mode="json")).json() == linked.json()
    retraction = service.Request(action="retracted", ticket_id="api-paid", expected_previous_id=linked.json()["id"],
        selection=None, reason="Signed explicit retraction", idempotency_key="api-retract")
    retracted = client.post(base, headers=headers, json=retraction.model_dump(mode="json"))
    assert retracted.status_code == 200 and retracted.json()["attribution"] == linked.json()["attribution"]
    assert client.get(base + "/original/api-retract", headers=headers).json() == retracted.json()


def test_postgres_conversion_originals_atomic_replay_retraction(postgres_flow, monkeypatch):
    exercise(postgres_flow[0], postgres_flow[1], monkeypatch)


def test_postgres_competing_conversion_keys_have_one_winner(postgres_flow, monkeypatch):
    engine, institute = postgres_flow[:2]; payload = setup(engine, institute, monkeypatch)
    def retain(key):
        selected = payload.model_copy(update={"idempotency_key": key, "selection": payload.selection.model_copy(update={"idempotency_key": key})})
        try:
            with Session(engine) as db: return service.execute(db, institute, selected, "manager")
        except HTTPException: return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(retain, ["competing-one", "competing-two"]))
    assert sum(o is not None for o in results) == 1
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ConversionOriginal)) == 1
        assert service.current(db, institute, payload.ticket_id) == next(o for o in results if o)
    winner = next(o for o in results if o)
    shared = payload.model_copy(update={"idempotency_key": "shared-correction", "expected_previous_id": winner.id,
        "selection": payload.selection.model_copy(update={"idempotency_key": "shared-correction"})})
    def recover():
        with Session(engine) as db: return service.execute(db, institute, shared, "manager")
    with ThreadPoolExecutor(max_workers=2) as pool:
        one, two = [future.result() for future in [pool.submit(recover), pool.submit(recover)]]
    assert one == two
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ConversionOriginal)) == 2
        assert service.current(db, institute, payload.ticket_id) == one
