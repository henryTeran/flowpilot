import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.modules.inventory import suppliers
from app.modules.inventory.models import StockSupplier, StockMovement
from app.modules.inventory.schemas import SupplierCreate
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow, race
import app.main as main_module


def terms(**changes):
    return {**dict(reference="SUP-001", name="Cabine Supplier", reason="Approved supplier identity", idempotency_key="supplier-original"), **changes}


def test_supplier_roles_scope_original_replay_and_no_stock_mutation(client):
    institute, _, _ = _bootstrap_reference_data(client)
    base = f"/api/v1/inventory/institutes/{institute}/suppliers"
    manager = _auth_headers("responsable_institut", institute)
    reception = _auth_headers(institute_id=institute)
    for headers in ({}, reception, _auth_headers("collaboratrice", institute),
                    _auth_headers("responsable_institut", "foreign"), _auth_headers("responsable_institut", None)):
        assert client.post(base, headers=headers, json=terms()).status_code == 403
    reply = client.post(base, headers=manager, json=terms())
    assert reply.status_code == 200
    original = reply.json()
    assert original["actor_id"] == "test-user" and original["created_at"].endswith("Z")
    assert client.post(base, headers=manager, json=terms()).json() == original
    assert client.get(base + "/" + original["id"], headers=reception).json() == original
    assert client.get(base, headers=reception).json() == [original]
    assert client.get(base + "?limit=1&offset=1", headers=reception).json() == []
    for changed in (terms(name="Changed"), terms(reference="OTHER"), terms(reason="Changed reason"), terms(idempotency_key="duplicate-reference")):
        assert client.post(base, headers=manager, json=changed).status_code == 400
    from app.core.security import create_access_token
    other = {"Authorization": "Bearer " + create_access_token(subject="other", extra_claims={"role": "responsable_institut", "institute_id": institute})}
    assert client.post(base, headers=other, json=terms()).status_code == 400
    foreign = "/api/v1/inventory/institutes/foreign/suppliers"
    foreign_manager = _auth_headers("responsable_institut", "foreign")
    assert client.get(foreign + "/" + original["id"], headers=foreign_manager).status_code == 404
    assert client.get(foreign, headers=foreign_manager).json() == []
    for payload in (terms(reference="bad spaces"), terms(reference=""), terms(name=" "), terms(reason="x"), {**terms(), "actor_id": "forged"}):
        assert client.post(base, headers=manager, json=payload).status_code == 422
    for query in ("limit=0", "limit=201", "offset=-1", "offset=100001"):
        assert client.get(base + "?" + query, headers=reception).status_code == 422
    with Session(main_module.engine) as db:
        assert db.scalar(select(func.count()).select_from(StockSupplier)) == 1
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 0


def test_postgres_concurrent_supplier_creation_preserves_one_original(postgres_flow):
    engine, institute, _, _ = postgres_flow
    payload = SupplierCreate(**terms())
    results = race(engine, [lambda db: suppliers.create(db, institute, payload, "signed"),
                            lambda db: suppliers.create(db, institute, payload, "signed")])
    assert len(results) == 2 and all(kind == "ok" for kind, _ in results)
    assert results[0][1] == results[1][1]
    with Session(engine) as db:
        rows = suppliers.list_suppliers(db, institute, 50, 0)
        assert len(rows) == 1 and rows[0].actor_id == "signed"
        original = rows[0].model_dump(mode="json")
        assert suppliers.create(db, institute, payload, "signed").model_dump(mode="json") == original
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 0
