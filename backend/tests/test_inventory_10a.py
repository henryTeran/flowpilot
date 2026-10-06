from decimal import Decimal
import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from fastapi import HTTPException
import app.main as main_module
from app.core.security import create_access_token
from app.modules.inventory import service
from app.modules.inventory.models import StockItem, StockMovement
from app.modules.inventory.schemas import ItemCreate, MovementCreate
from app.modules.institutes.models import Institute
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow, race


def item(**changes):
    return {**dict(sku="SERUM", name="Serum", category="cabine", unit="ml", reorder_threshold="4.125",
        reason="Catalogue initial", idempotency_key="catalogue"), **changes}


def movement(**changes):
    return {**dict(kind="receipt", quantity="10.125", reason="Livraison recue", idempotency_key="delivery"), **changes}


def test_exact_stock_history_replay_units_and_scoped_reads(client):
    institute, _, _ = _bootstrap_reference_data(client)
    base = f"/api/v1/inventory/institutes/{institute}"
    manager = _auth_headers("responsable_institut", institute)
    operator = _auth_headers(institute_id=institute)
    created = client.post(base + "/items", headers=manager, json=item())
    assert created.status_code == 200
    row = created.json()
    assert (row["on_hand"], row["reorder_threshold"], row["at_or_below_threshold"]) == ("0.000", "4.125", True)
    assert row["created_at"].endswith("Z") or row["created_at"].endswith("+00:00")
    path = base + f"/items/{row['id']}"
    first = client.post(path + "/movements", headers=manager, json=movement())
    assert first.status_code == 200
    assert first.json()["quantity"] == "10.125"
    assert client.post(path + "/movements", headers=manager, json=movement()).json() == first.json()
    deduction = movement(kind="adjustment", quantity="-6.000", reason="Inventaire physique", idempotency_key="count")
    assert client.post(path + "/movements", headers=manager, json=deduction).status_code == 200
    assert client.get(path, headers=operator).json()["on_hand"] == "4.125"
    assert client.get(path, headers=operator).json()["at_or_below_threshold"] is True
    assert client.get(base + "/items", headers=operator).json()[0]["on_hand"] == "4.125"
    assert client.post(base + "/items", headers=manager, json=item()).json()["id"] == row["id"]
    assert client.post(path + "/movements", headers=manager, json=deduction).status_code == 200  # replay before depleted-budget check
    assert len(client.get(path + "/movements", headers=operator).json()) == 2
    assert len(client.get(path + "/movements?limit=1&offset=1", headers=operator).json()) == 1
    for changed in (movement(quantity="11.125"), movement(reason="Autre livraison"), movement(kind="adjustment")):
        assert client.post(path + "/movements", headers=manager, json=changed).status_code == 400
    assert client.post(path + "/movements", headers=manager, json=movement(kind="adjustment", quantity="-4.126", idempotency_key="overdraw")).status_code == 400
    assert client.post(base + "/items", headers=manager, json=item(name="Changed")).status_code == 400
    assert client.post(base + "/items", headers=manager, json=item(idempotency_key="duplicate-sku")).status_code == 400
    other_actor = {"Authorization": "Bearer " + create_access_token(subject="other", extra_claims={"role": "responsable_institut", "institute_id": institute})}
    assert client.post(path + "/movements", headers=other_actor, json=movement()).status_code == 400
    assert client.post(base + "/items", headers=other_actor, json=item()).status_code == 400
    assert client.get(path, headers=_auth_headers("responsable_institut", "foreign")).status_code == 403
    assert client.get(base + "/items/missing", headers=operator).status_code == 404
    for bad in ("0", "-1", "0.0001", "NaN", "Infinity", "1000000000000"):
        assert client.post(path + "/movements", headers=manager, json=movement(quantity=bad, idempotency_key="invalid")).status_code in {400, 422}
    assert client.get(path, headers=operator).json()["on_hand"] == "4.125"


def test_inventory_roles_and_explicit_whole_units(client):
    institute, _, _ = _bootstrap_reference_data(client)
    base = f"/api/v1/inventory/institutes/{institute}"
    manager = _auth_headers("responsable_institut", institute)
    for headers in ({}, _auth_headers(institute_id=institute), _auth_headers("collaboratrice", institute),
                    _auth_headers("responsable_institut", None), _auth_headers("responsable_institut", "foreign")):
        assert client.post(base + "/items", headers=headers, json=item()).status_code == 403
    assert client.post(base + "/items", headers=manager, json=item(unit="unit")).status_code == 400
    row = client.post(base + "/items", headers=manager, json=item(unit="unit", reorder_threshold="2", category="consumable")).json()
    path = base + f"/items/{row['id']}/movements"
    assert client.post(path, headers=manager, json=movement(quantity="0.5")).status_code == 400
    assert client.post(path, headers=_auth_headers(institute_id=institute), json=movement(quantity="5")).status_code == 403
    assert client.post(path, headers=manager, json=movement(quantity="5")).status_code == 200
    for payload in (item(unit="litre"), item(category="unknown"), {**item(), "on_hand": "999"}):
        assert client.post(base + "/items", headers=manager, json=payload).status_code == 422
    assert client.get(base + "/items?limit=201", headers=manager).status_code == 422


def test_inventory_foreign_item_is_hidden_and_same_sku_is_tenant_local(client):
    institute, _, _ = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        original = db.get(Institute, institute)
        db.add(Institute(id="inventory-other", region_id=original.region_id, name="Other", city="Other", timezone=original.timezone, status="active"))
        db.commit()
    base = f"/api/v1/inventory/institutes/{institute}"
    foreign = "/api/v1/inventory/institutes/inventory-other"
    own = _auth_headers("responsable_institut", institute)
    other = _auth_headers("responsable_institut", "inventory-other")
    row = client.post(base + "/items", headers=own, json=item()).json()
    assert client.post(foreign + "/items", headers=other, json=item()).status_code == 200
    for suffix in ("", "/movements"):
        assert client.get(foreign + f"/items/{row['id']}" + suffix, headers=other).status_code == 404
    assert client.post(foreign + f"/items/{row['id']}/movements", headers=other, json=movement()).status_code == 404
    assert client.get(base + "/items", headers=other).status_code == 403
    assert client.get(base + "/items", headers=own).json()[0]["on_hand"] == "0.000"


def test_stock_sqlite_large_fraction_is_exact_and_failed_commit_leaves_no_movement(client):
    institute, _, _ = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        row = service.create_item(db, institute, ItemCreate(**item(unit="g", reorder_threshold="0")), "manager")
        service.move(db, institute, row.id, MovementCreate(**movement(quantity="999999999999.998")), "manager")
        def fail(db, context, instances):
            if any(isinstance(row, StockMovement) for row in db.new):
                raise RuntimeError("Injected stock commit failure")
        event.listen(Session, "before_flush", fail)
        try:
            with pytest.raises(RuntimeError, match="Injected stock"):
                service.move(db, institute, row.id, MovementCreate(**movement(quantity="0.001", idempotency_key="last")), "manager")
            db.rollback()
        finally:
            event.remove(Session, "before_flush", fail)
        assert service.balance_milli(db, institute, row.id) == 999999999999998
        last = MovementCreate(**movement(quantity="0.001", idempotency_key="last"))
        service.move(db, institute, row.id, last, "manager")
        assert service.read_item(service.require_item(db, institute, row.id), service.balance_milli(db, institute, row.id)).on_hand == Decimal("999999999999.999")
        with pytest.raises(HTTPException):
            service.move(db, institute, row.id, MovementCreate(**movement(quantity="0.001", idempotency_key="overflow")), "manager")


def test_postgres_stock_replay_and_competing_deductions(postgres_flow):
    engine, institute, _, _ = postgres_flow
    catalogue = ItemCreate(**item())
    created = race(engine, [lambda db: service.create_item(db, institute, catalogue, "manager")] * 2)
    assert all(result[0] == "ok" for result in created) and created[0][1] == created[1][1]
    with Session(engine) as db:
        row = db.get(StockItem, created[0][1])
    delivery = MovementCreate(**movement())
    results = race(engine, [lambda db: service.move(db, institute, row.id, delivery, "manager")] * 2)
    assert all(result[0] == "ok" for result in results) and results[0][1] == results[1][1]
    results = race(engine, [lambda db: service.move(db, institute, row.id, MovementCreate(**movement(kind="adjustment", quantity="-6", idempotency_key="deduct-a")), "manager"),
                            lambda db: service.move(db, institute, row.id, MovementCreate(**movement(kind="adjustment", quantity="-6", idempotency_key="deduct-b")), "manager")])
    assert sorted(result[0] for result in results) == ["conflict", "ok"]
    with Session(engine) as db:
        assert service.balance_milli(db, institute, row.id) == 4125
        assert len(list(db.scalars(select(StockMovement)))) == 2
