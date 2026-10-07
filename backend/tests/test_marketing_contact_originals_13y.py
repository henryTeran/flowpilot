from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select, func
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.marketing import contacts, contact_originals as service
from app.modules.marketing.models import ContactHead, ContactOriginal
from test_crm_billing_12b import NOW, seed
from test_marketing_contacts_13w import declaration
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def body(institute, customer="customer_crm", key="first", previous=None, permission="granted"):
    value = declaration(permission).declaration.model_dump()
    value.update(institute_id=institute, customer_id=customer)
    return contacts.Request(declaration=value, previous_id=previous, reason="Explicit marketing contact declaration", idempotency_key=key)


def exercise(engine, institute, monkeypatch):
    monkeypatch.setattr(service, "utcnow", lambda: NOW)
    with Session(engine) as db:
        seed(db, institute); db.commit()
        assert service.current(db, institute, "customer_crm") is None
        first = service.create(db, institute, "customer_crm", body(institute), "manager")
        second = service.create(db, institute, "customer_crm", body(institute, key="withdraw", previous=first.id, permission="refused"), "manager")
        assert second.previous_id == first.id and service.current(db, institute, "customer_crm") == second
        assert service.require(db, institute, "customer_crm", first.id) == first
        assert service.original(db, institute, "customer_crm", "first") == first
        def fail(session, context, instances):
            if any(isinstance(row, ContactHead) for row in session.dirty): raise RuntimeError("Injected contact head failure")
        event.listen(db, "before_flush", fail)
        try:
            with pytest.raises(RuntimeError, match="head failure"):
                service.create(db, institute, "customer_crm", body(institute, key="rollback", previous=second.id), "manager")
        finally: event.remove(db, "before_flush", fail)
        assert service.original(db, institute, "customer_crm", "rollback") is None
        assert service.current(db, institute, "customer_crm") == second
        # Original replay occurs before reading the current head or clock.
        def clock_fail(): raise AssertionError("Replay consulted clock")
        monkeypatch.setattr(service, "utcnow", clock_fail)
        assert service.create(db, institute, "customer_crm", body(institute), "manager") == first
        with monkeypatch.context() as guarded:
            guarded.setattr(service, "head", lambda *args: clock_fail())
            assert service.create(db, institute, "customer_crm", body(institute), "manager") == first
        for payload, actor in [(body(institute), "other"), (body(institute, permission="refused"), "manager"),
                (body(institute, customer="customer_other"), "manager"), (body(institute), " manager ")]:
            with pytest.raises(HTTPException): service.create(db, institute, payload.declaration.customer_id, payload, actor)
        monkeypatch.setattr(service, "utcnow", lambda: NOW - timedelta(microseconds=1))
        for payload in [body(institute, key="stale", previous=first.id), body(institute, key="clock", previous=second.id)]:
            with pytest.raises(HTTPException): service.create(db, institute, "customer_crm", payload, "manager")
        for customer in ["customer_foreign", "historical_opaque"]:
            with pytest.raises(HTTPException): service.current(db, institute, customer)
        with pytest.raises(HTTPException): service.require(db, institute, "customer_other", first.id)
        with pytest.raises(HTTPException): service.original(db, institute, "customer_other", "first")
        assert db.scalar(select(func.count()).select_from(ContactOriginal)) == 2
        monkeypatch.setattr(service, "utcnow", lambda: NOW)
        return first


def test_sqlite_contacts_atomic_recovery_signed_roles_and_scoped_reads(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    first = exercise(main_module.engine, institute, monkeypatch)
    path = f"/api/v1/marketing/institutes/{institute}/customers/customer_other/contact-declarations"
    headers = _auth_headers("responsable_institut", institute)
    reply = client.post(path, json=body(institute, "customer_other", "http").model_dump(mode="json"), headers=headers)
    assert reply.status_code == 200, reply.text
    value = reply.json()
    assert {c["channel"] for c in value["declaration"]["communications"]} == {"email", "sms", "push"}
    assert client.get(path + "/original/http", headers=headers).json() == value
    assert client.get(path + "/" + value["id"], headers=headers).json() == value
    assert client.get(path + "/current", headers=headers).json() == value
    assert client.post(path, json=body(institute, "customer_other", "http").model_dump(mode="json"), headers=headers).json() == value
    assert client.get(path + "/" + first.id, headers=headers).status_code == 404
    assert client.get(path + "/original/first", headers=headers).status_code == 400
    for role, owner in [("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")]:
        denied = _auth_headers(role, owner)
        assert client.post(path, json=body(institute, "customer_other", "forged").model_dump(mode="json"), headers=denied).status_code == 403
        for suffix in ["/current", "/original/http", "/" + value["id"]]: assert client.get(path + suffix, headers=denied).status_code == 403
    assert client.post(path, json=body(institute, "customer_other", "anonymous").model_dump(mode="json")).status_code == 403
    wrong_scope = body("foreign", "customer_other", "wrong-scope").model_dump(mode="json")
    assert client.post(path, json=wrong_scope, headers=headers).status_code == 400
    assert client.get(path.replace("customer_other", "customer_foreign") + "/current", headers=headers).status_code == 404
    injected_actor = body(institute, "customer_other", "injected").model_dump(mode="json"); injected_actor["actor_id"] = "forged"
    assert client.post(path, json=injected_actor, headers=headers).status_code == 422


def test_postgres_contacts_atomic_recovery(postgres_flow, monkeypatch):
    exercise(postgres_flow[0], postgres_flow[1], monkeypatch)


@pytest.mark.parametrize("same_key", [True, False])
def test_postgres_serializes_contact_replays_and_competing_predecessors(postgres_flow, monkeypatch, same_key):
    engine, institute = postgres_flow[:2]; monkeypatch.setattr(service, "utcnow", lambda: NOW)
    with Session(engine) as db:
        seed(db, institute); db.commit()
        first = service.create(db, institute, "customer_crm", body(institute), "manager")
    def run(key):
        with Session(engine) as db:
            try: return service.create(db, institute, "customer_crm", body(institute, key=key, previous=first.id, permission="refused"), "manager")
            except HTTPException as error:
                assert error.status_code == 400
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, "one"), pool.submit(run, "one" if same_key else "two")]
        values = [f.result(timeout=15) for f in futures]
    if same_key: assert values[0] == values[1] and values[0] is not None
    else: assert sum(v is not None for v in values) == 1
    with Session(engine) as db:
        assert service.current(db, institute, "customer_crm") == next(v for v in values if v is not None)
        assert db.scalar(select(func.count()).select_from(ContactOriginal)) == 2
        assert service.require(db, institute, "customer_crm", first.id) == first


def test_corrupt_retained_scope_refuses_contact_reads_and_new_writes(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client); monkeypatch.setattr(service, "utcnow", lambda: NOW)
    with Session(main_module.engine) as db:
        seed(db, institute); db.commit()
        first = service.create(db, institute, "customer_crm", body(institute), "manager")
        row = db.get(ContactOriginal, first.id)
        row.declaration = {**row.declaration, "customer_id": "customer_other"}; db.commit()
        for read in [lambda: service.current(db, institute, "customer_crm"), lambda: service.require(db, institute, "customer_crm", first.id),
                     lambda: service.original(db, institute, "customer_crm", "first"),
                     lambda: service.create(db, institute, "customer_crm", body(institute, key="new", previous=first.id), "manager")]:
            with pytest.raises(HTTPException, match="ownership is incoherent"): read()
        assert db.scalar(select(func.count()).select_from(ContactOriginal)) == 1
        assert db.get(ContactHead, (institute, "customer_crm")).original_id == first.id
        row.declaration = first.declaration.model_dump(mode="json"); db.commit()
        for field in ("reason", "idempotency_key"):
            exact = getattr(row, field)
            setattr(row, field, " " + exact); db.commit()
            with pytest.raises(HTTPException, match="terms are incoherent"):
                service.require(db, institute, "customer_crm", first.id)
            setattr(row, field, exact); db.commit()
        assert service.current(db, institute, "customer_crm") == first
