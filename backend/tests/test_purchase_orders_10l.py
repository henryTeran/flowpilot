import pytest
from sqlalchemy import select, func, event, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
import app.main as main_module
from app.modules.inventory import service as stock, suppliers, orders
from app.modules.inventory.models import StockPurchaseOrder, StockPurchaseReceipt, StockPurchaseReceiptLine, StockMovement
from app.modules.inventory.schemas import ItemCreate, SupplierCreate, MovementCreate
from app.modules.inventory.order_schemas import OrderCreate, ReceiptCreate
from test_inventory_10a import item, movement
from test_stock_suppliers_10k import terms as supplier_terms
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow, race


def setup(db, institute):
    supplier = suppliers.create(db, institute, SupplierCreate(**supplier_terms()), "manager")
    serum = stock.create_item(db, institute, ItemCreate(**item()), "manager")
    cartridge = stock.create_item(db, institute, ItemCreate(**item(sku="CARTRIDGE", name="Cartridge", unit="unit", reorder_threshold="1", idempotency_key="second-item")), "manager")
    payload = dict(supplier_id=supplier.id, reference="PO-001", entries=[dict(item_id=serum.id, unit="ml", quantity="10.125"),
        dict(item_id=cartridge.id, unit="unit", quantity="2")], reason="Explicit purchase order", idempotency_key="order-original")
    return serum.id, cartridge.id, payload


def reception(item_id, quantity="2.125", **changes):
    return {**dict(entries=[dict(item_id=item_id, unit="ml", quantity=quantity)], reason="Physical partial receipt", idempotency_key="receipt-original"), **changes}


def test_http_immutable_order_exact_partial_receipts_and_original_recovery(client):
    institute, _, _ = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        serum, cartridge, payload = setup(db, institute)
    base = f"/api/v1/inventory/institutes/{institute}"
    manager = _auth_headers("responsable_institut", institute)
    reader = _auth_headers(institute_id=institute)
    first = client.post(base + "/orders", headers=manager, json=payload)
    assert first.status_code == 200, first.text
    original = first.json()
    assert original["actor_id"] == "test-user" and original["created_at"].endswith("Z")
    path = base + "/orders/" + original["id"]
    assert client.post(base + "/orders", headers=manager, json=payload).json() == original
    assert client.get(path, headers=reader).json() == original
    assert client.get(base + "/orders", headers=reader).json() == [original]
    assert client.get(base + f"/items/{serum}", headers=reader).json()["on_hand"] == "0.000"
    assert client.get(path + "/progress", headers=reader).json()["state"] == "pending"
    receipt_payload = reception(serum)
    reply = client.post(path + "/receipts", headers=manager, json=receipt_payload)
    assert reply.status_code == 200, reply.text
    receipt = reply.json()
    assert receipt["entries"][0]["quantity"] == "2.125" and receipt["occurred_at"].endswith("Z")
    assert client.get(base + "/purchase-receipts/" + receipt["id"], headers=reader).json() == receipt
    assert client.get(path + "/receipts", headers=reader).json() == [receipt]
    progress = client.get(path + "/progress", headers=reader).json()
    assert progress["state"] == "partial"
    assert next(row for row in progress["entries"] if row["item_id"] == serum)["remaining"] == "8.000"
    finish = dict(entries=[dict(item_id=serum, unit="ml", quantity="8"), dict(item_id=cartridge, unit="unit", quantity="2")], reason="Remaining physical delivery", idempotency_key="remaining")
    assert client.post(path + "/receipts", headers=manager, json=finish).status_code == 200
    assert client.get(path + "/progress", headers=reader).json()["state"] == "received"
    assert client.post(path + "/receipts", headers=manager, json=receipt_payload).json() == receipt
    assert client.post(base + "/orders", headers=manager, json=payload).json() == original
    assert client.post(path + "/receipts", headers=manager, json=reception(serum, idempotency_key="over-receipt")).status_code == 400
    assert client.post(path + "/receipts", headers=manager, json=reception(serum, reason="Changed reason")).status_code == 400
    assert client.post(base + "/orders", headers=manager, json={**payload, "reference": "CHANGED"}).status_code == 400
    history = client.get(base + f"/items/{serum}/movements", headers=reader).json()
    assert len(history) == 2 and history[0]["id"] == receipt["entries"][0]["movement_id"]
    assert client.get(base + f"/items/{serum}", headers=reader).json()["on_hand"] == "10.125"
    for headers in ({}, reader, _auth_headers("collaboratrice", institute), _auth_headers("responsable_institut", "foreign")):
        assert client.post(base + "/orders", headers=headers, json=payload).status_code == 403
        assert client.post(path + "/receipts", headers=headers, json=receipt_payload).status_code == 403
    foreign = "/api/v1/inventory/institutes/foreign"
    foreign_reader = _auth_headers(institute_id="foreign")
    for suffix in (f"/orders/{original['id']}", f"/orders/{original['id']}/progress", f"/orders/{original['id']}/receipts", f"/purchase-receipts/{receipt['id']}"):
        assert client.get(foreign + suffix, headers=foreign_reader).status_code == 404
    for invalid in ({**payload, "actor_id": "forged"}, {**payload, "entries": []}, {**payload, "entries": payload["entries"] * 2}):
        assert client.post(base + "/orders", headers=manager, json=invalid).status_code == 422
    for quantity in ("0", "-1", "0.0001", "NaN", "Infinity"):
        assert client.post(path + "/receipts", headers=manager, json=reception(serum, quantity, idempotency_key="invalid")).status_code == 422


def test_postgres_competing_partial_receipts_do_not_overreceive_and_replay_after_completion(postgres_flow):
    engine, institute, _, _ = postgres_flow
    with Session(engine) as db:
        serum, _, payload = setup(db, institute)
        order = orders.create(db, institute, OrderCreate(**payload), "manager")
        identifier = order.id
    results = race(engine, [lambda db: orders.receive(db, institute, identifier, ReceiptCreate(**reception(serum, "8", idempotency_key="a")), "manager"),
                            lambda db: orders.receive(db, institute, identifier, ReceiptCreate(**reception(serum, "8", idempotency_key="b")), "manager")])
    assert sorted(kind for kind, _ in results) == ["conflict", "ok"]
    with Session(engine) as db:
        assert stock.balance_milli(db, institute, serum) == 8000
        assert db.scalar(select(func.count()).select_from(StockPurchaseReceipt)) == 1
        original = db.scalar(select(StockPurchaseReceipt))
        replay = ReceiptCreate(**reception(serum, "8", idempotency_key=original.idempotency_key))
        assert orders.receive(db, institute, identifier, replay, "manager").id == original.id
        with pytest.raises(HTTPException):
            orders.receive(db, institute, identifier, replay, "different-actor")
        db.rollback()
        receipt = db.scalar(select(StockPurchaseReceiptLine))
        with pytest.raises(IntegrityError, match="fk_stock_purchase_receipt_movement"):
            with db.begin_nested():
                db.execute(text("UPDATE stock_purchase_receipt_lines SET movement_id='foreign-movement' WHERE receipt_id=:id"), dict(id=receipt.receipt_id))


def test_postgres_multiline_validation_and_failure_roll_back_all_receipt_facts(postgres_flow):
    engine, institute, _, _ = postgres_flow
    with Session(engine) as db:
        serum, cartridge, payload = setup(db, institute)
        identifier = orders.create(db, institute, OrderCreate(**payload), "manager").id
        invalid = ReceiptCreate(entries=[dict(item_id=serum, unit="ml", quantity="1"), dict(item_id=cartridge, unit="unit", quantity="3")], reason="Too many cartridges", idempotency_key="invalid")
        with pytest.raises(HTTPException):
            orders.receive(db, institute, identifier, invalid, "manager")
        db.rollback()
        def fail(mapper, connection, target):
            raise RuntimeError("Injected receipt-line write failure")
        event.listen(StockPurchaseReceiptLine, "before_insert", fail)
        try:
            with pytest.raises(RuntimeError, match="Injected"):
                orders.receive(db, institute, identifier, ReceiptCreate(**reception(serum)), "manager")
        finally:
            event.remove(StockPurchaseReceiptLine, "before_insert", fail)
            db.rollback()
        assert db.scalar(select(func.count()).select_from(StockPurchaseReceipt)) == 0
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 0
        assert stock.balance_milli(db, institute, serum) == 0
        assert orders.progress(db, institute, identifier).state == "pending"


def test_postgres_order_replay_concurrency_and_receipt_replay_before_current_capacity(postgres_flow):
    engine, institute, _, _ = postgres_flow
    with Session(engine) as db:
        serum, _, payload = setup(db, institute)
    results = race(engine, [lambda db: orders.create(db, institute, OrderCreate(**payload), "manager"),
                            lambda db: orders.create(db, institute, OrderCreate(**payload), "manager")])
    assert results[0] == results[1] and results[0][0] == "ok"
    with Session(engine) as db:
        identifier = results[0][1]
        request = ReceiptCreate(**reception(serum))
        original = orders.receive(db, institute, identifier, request, "manager").model_dump(mode="json")
        remaining_capacity = stock.MAX_MILLI - 2125
        from decimal import Decimal
        stock.move(db, institute, serum, MovementCreate(**movement(quantity=str(Decimal(remaining_capacity) / 1000), idempotency_key="fill-capacity")), "manager")
        assert orders.receive(db, institute, identifier, request, "manager").model_dump(mode="json") == original
        with pytest.raises(HTTPException):
            orders.receive(db, institute, identifier, ReceiptCreate(**reception(serum, "1", idempotency_key="over-capacity")), "manager")
        db.rollback()
        assert stock.balance_milli(db, institute, serum) == stock.MAX_MILLI
        assert db.scalar(select(func.count()).select_from(StockPurchaseReceipt)) == 1
        with pytest.raises(IntegrityError, match="fk_stock_order_supplier_owner"):
            with db.begin_nested():
                db.execute(text("UPDATE stock_purchase_orders SET supplier_id='foreign-supplier' WHERE id=:id"), dict(id=identifier))


def test_bounded_order_and_receipt_lists_do_not_read_each_header_separately(client):
    institute, _, _ = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        serum, _, payload = setup(db, institute)
        identifier = orders.create(db, institute, OrderCreate(**payload), "manager").id
        orders.create(db, institute, OrderCreate(**{**payload, "reference": "PO-002", "idempotency_key": "second-order"}), "manager")
        orders.receive(db, institute, identifier, ReceiptCreate(**reception(serum, "1", idempotency_key="first")), "manager")
        orders.receive(db, institute, identifier, ReceiptCreate(**reception(serum, "1", idempotency_key="second")), "manager")
        queries = []
        def record(connection, cursor, statement, parameters, context, many):
            if statement.lstrip().upper().startswith("SELECT"):
                queries.append(statement)
        event.listen(main_module.engine, "before_cursor_execute", record)
        try:
            assert len(orders.list_orders(db, institute, 50, 0)) == 2
            assert len(queries) == 2 and "LIMIT" in queries[0]
            queries.clear()
            assert len(orders.list_receipts(db, institute, identifier, 50, 0)) == 2
            assert len(queries) == 3 and "LIMIT" in queries[1]
        finally:
            event.remove(main_module.engine, "before_cursor_execute", record)
