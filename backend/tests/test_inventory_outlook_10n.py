from decimal import localcontext
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
import pytest
from sqlalchemy import event, select, func, text
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.inventory import outlook, orders, recipes, service as stock
from app.modules.inventory.models import StockMovement, StockPurchaseOrder, StockPurchaseReceipt
from app.modules.inventory.schemas import RecipeCreate, MovementCreate
from app.modules.inventory.order_schemas import OrderCreate, ReceiptCreate
from app.modules.inventory.outlook_schemas import ForecastScenario
from app.modules.institutes.models import Institute
from test_purchase_orders_10l import setup, reception
from test_stock_recipes_10c import payload as recipe_terms
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def scenario(service_id, recipe_id, quantity=3):
    return dict(starts_at="2026-10-07T09:00:00+02:00", ends_at="2026-10-14T09:00:00+02:00",
        demands=[dict(service_id=service_id, recipe_id=recipe_id, quantity=quantity)])


def test_http_reorder_and_pinned_norm_scenarios_are_exact_readonly_and_scoped(client):
    institute, _, services = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        serum, cartridge, terms = setup(db, institute)
        order = orders.create(db, institute, OrderCreate(**terms), "manager")
        orders.receive(db, institute, order.id, ReceiptCreate(**reception(serum)), "manager")
        original = recipes.create(db, institute, services[0]["id"], RecipeCreate(**recipe_terms(serum)), "manager")
        newer = recipes.create(db, institute, services[0]["id"], RecipeCreate(**recipe_terms(serum,
            base_revision=1, entries=[dict(item_id=serum, quantity="8.250")], idempotency_key="new-norm")), "manager")
        disabled = recipes.create(db, institute, services[1]["id"], RecipeCreate(**recipe_terms(serum,
            enabled=False, entries=[], idempotency_key="disabled-norm")), "manager")
        before = {model: db.scalar(select(func.count()).select_from(model)) for model in (StockMovement, StockPurchaseOrder, StockPurchaseReceipt)}
        db.add(Institute(id="foreign", region_id=db.get(Institute, institute).region_id,
            city="Foreign", name="Foreign scenario scope", timezone="UTC")); db.commit()
    base = f"/api/v1/inventory/institutes/{institute}"
    reader = _auth_headers(institute_id=institute)
    result = client.get(base + "/outlook", headers=reader)
    assert result.status_code == 200, result.text
    snapshot = result.json()
    row = next(row for row in snapshot["items"] if row["item_id"] == serum)
    assert snapshot["coverage"] == "not_applicable" and snapshot["starts_at"] is None
    assert (row["on_hand"], row["threshold_shortfall"], row["pending_order_quantity"]) == ("2.125", "2.000", "8.000")
    assert row["complete_demand"] is None and row["conditional_shortfall_after_all_orders"] == "0.000"
    body = scenario(services[0]["id"], original.id)
    forecast = client.post(base + "/forecast", headers=reader, json=body)
    assert forecast.status_code == 200, forecast.text
    data = forecast.json(); row = next(row for row in data["items"] if row["item_id"] == serum)
    assert data["source"] == "explicit_service_volume_scenario" and data["coverage"] == "complete_selected_norms"
    assert data["starts_at"] == "2026-10-07T07:00:00Z"
    assert data["demands"][0]["recipe_id"] == original.id and data["demands"][0]["recipe_revision"] == 1
    assert row["known_demand"] == row["complete_demand"] == "12.375"  # Original, never newer 8.250 norm.
    assert (row["known_demand_shortfall"], row["conditional_shortfall_after_all_orders"]) == ("14.375", "6.375")
    partial = {**body, "demands": [*body["demands"], dict(service_id=services[1]["id"], recipe_id=None, quantity=2)]}
    data = client.post(base + "/forecast", headers=reader, json=partial).json()
    assert data["coverage"] == "partial_selected_norms" and all(row["complete_demand"] is None for row in data["items"])
    assert data["demands"][1]["state"] == "missing_selected_norm"
    zero = client.post(base + "/forecast", headers=reader, json=scenario(services[1]["id"], disabled.id)).json()
    assert zero["coverage"] == "complete_selected_norms" and all(row["complete_demand"] == "0.000" for row in zero["items"])
    page1 = client.get(base + "/outlook?limit=1", headers=reader).json()
    page2 = client.get(base + "/outlook?limit=1&offset=1", headers=reader).json()
    assert len(page1["items"]) == len(page2["items"]) == 1 and page1["items"][0]["item_id"] != page2["items"][0]["item_id"]
    for auth in ({}, _auth_headers("collaboratrice", institute), _auth_headers("responsable_institut", "foreign")):
        assert client.get(base + "/outlook", headers=auth).status_code == 403
        assert client.post(base + "/forecast", headers=auth, json=body).status_code == 403
    assert client.post(base + "/forecast", headers=reader, json=scenario(services[1]["id"], original.id)).status_code == 404
    assert client.post("/api/v1/inventory/institutes/foreign/forecast", headers=_auth_headers(institute_id="foreign"), json=body).status_code == 404
    foreign = client.get("/api/v1/inventory/institutes/foreign/outlook", headers=_auth_headers(institute_id="foreign")).json()
    assert foreign["items"] == [] and foreign["institute_id"] == "foreign"
    for bad in ({**body, "starts_at": "2026-10-07T09:00:00"}, {**body, "ends_at": body["starts_at"]},
                {**body, "ends_at": "2028-10-07T09:00:00Z"}, {**body, "demands": body["demands"] * 2},
                {**body, "actor_id": "forged"}, scenario(services[0]["id"], original.id, True), scenario(services[0]["id"], original.id, 0)):
        assert client.post(base + "/forecast", headers=reader, json=bad).status_code == 422
    assert client.get(base + "/outlook?limit=201", headers=reader).status_code == 422
    with Session(main_module.engine) as db:
        assert before == {model: db.scalar(select(func.count()).select_from(model)) for model in before}
        # Stock depletion does not undo the recorded incoming-order remainder.
        stock.move(db, institute, serum, MovementCreate(kind="adjustment", quantity="-2.125", reason="Physical count", idempotency_key="deplete"), "manager")
        row = next(row for row in outlook.read(db, institute, 50, 0).items if row.item_id == serum)
        assert row.pending_order_quantity == "8.000" and row.on_hand == "0.000"


def test_pending_orders_do_not_double_count_partial_receipts_or_manual_stock_entries(client):
    institute, _, _ = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        serum, cartridge, terms = setup(db, institute)
        first = orders.create(db, institute, OrderCreate(**terms), "manager")
        orders.receive(db, institute, first.id, ReceiptCreate(**reception(serum)), "manager")
        orders.receive(db, institute, first.id, ReceiptCreate(**reception(serum, "3", idempotency_key="second-part")), "manager")
        second = orders.create(db, institute, OrderCreate(**{**terms, "reference": "PO-2", "idempotency_key": "po-2"}), "manager")
        orders.receive(db, institute, second.id, ReceiptCreate(**reception(serum, "10.125", idempotency_key="all-second")), "manager")
        orders.create(db, institute, OrderCreate(**{**terms, "reference": "PO-3", "idempotency_key": "po-3",
            "entries": [dict(item_id=serum, unit="ml", quantity="4.125")]}), "manager")
        stock.move(db, institute, serum, MovementCreate(kind="receipt", quantity="2", reason="Unrelated receipt", idempotency_key="manual"), "manager")
        result = outlook.read(db, institute, 50, 0)
        row = next(row for row in result.items if row.item_id == serum)
        assert (row.on_hand, row.pending_order_quantity, row.threshold_shortfall) == ("17.250", "9.125", "0.000")
        row = next(row for row in result.items if row.item_id == cartridge)
        assert (row.on_hand, row.threshold_shortfall, row.pending_order_quantity) == ("0.000", "1.000", "4.000")
        assert row.at_or_below_threshold is True and row.conditional_shortfall_after_all_orders == "0.000"
        stock.move(db, institute, serum, MovementCreate(kind="adjustment", quantity="-13.125", reason="Count at threshold", idempotency_key="threshold"), "manager")
        row = next(row for row in outlook.read(db, institute, 50, 0).items if row.item_id == serum)
        assert row.on_hand == row.threshold == "4.125" and row.at_or_below_threshold is True
        assert row.threshold_shortfall == "0.000" and row.pending_order_quantity == "9.125"


def test_forecast_query_count_is_constant_and_big_integer_projection_preserves_precision(client):
    institute, _, services = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        serum, _, terms = setup(db, institute)
        original = recipes.create(db, institute, services[0]["id"], RecipeCreate(**recipe_terms(serum,
            entries=[dict(item_id=serum, quantity="999999999999.999")])), "manager")
        orders.create(db, institute, OrderCreate(**terms), "manager")
        queries = []
        def record(_conn, _cursor, statement, _params, _context, _many):
            if statement.lstrip().upper().startswith("SELECT"):
                queries.append(statement)
        event.listen(main_module.engine, "before_cursor_execute", record)
        try:
            with localcontext() as context:
                context.prec = 6
                result = outlook.read(db, institute, 50, 0, ForecastScenario(**scenario(services[0]["id"], original.id, 100000)))
            row = next(row for row in result.items if row.item_id == serum)
            assert row.known_demand == "99999999999999900.000"
            assert row.known_demand_shortfall == "99999999999999904.125"
            assert len(queries) == 7 and any("LIMIT" in query for query in queries)
        finally:
            event.remove(main_module.engine, "before_cursor_execute", record)


def test_postgres_outlook_waits_for_atomic_receipt_then_reads_stock_and_pending_together(postgres_flow):
    engine, institute, _, service_id = postgres_flow
    with Session(engine) as db:
        serum, _, terms = setup(db, institute)
        original = orders.create(db, institute, OrderCreate(**terms), "manager")
        norm = recipes.create(db, institute, service_id, RecipeCreate(**recipe_terms(serum)), "manager")
    staged, release, reading = Event(), Event(), Event()
    reader_pid = []
    def writer():
        with Session(engine) as db:
            def hold(_db):
                staged.set(); assert release.wait(10)
            event.listen(db, "before_commit", hold, once=True)
            return orders.receive(db, institute, original.id, ReceiptCreate(**reception(serum)), "manager")
    def reader():
        with Session(engine) as db:
            reader_pid.append(db.scalar(text("select pg_backend_pid()")))
            reading.set()
            return outlook.read(db, institute, 50, 0, ForecastScenario(**scenario(service_id, norm.id)))
    with ThreadPoolExecutor(max_workers=2) as pool:
        write = pool.submit(writer); assert staged.wait(5)
        read = pool.submit(reader); assert reading.wait(5)
        try:
            deadline = time.monotonic() + 5
            with Session(engine) as observer:
                while time.monotonic() < deadline:
                    waiting = observer.scalar(text("select wait_event_type from pg_stat_activity where pid=:pid"), {"pid": reader_pid[0]})
                    if waiting == "Lock":
                        break
                    observer.rollback(); time.sleep(.01)
            assert waiting == "Lock" and not read.done()
        finally:
            release.set()
        receipt = write.result(timeout=5)
        row = next(row for row in read.result(timeout=5).items if row.item_id == serum)
        assert receipt.entries[0].quantity == 2.125
        assert (row.on_hand, row.pending_order_quantity, row.threshold_shortfall) == ("2.125", "8.000", "2.000")
        assert row.known_demand == "12.375" and row.known_demand_shortfall == "14.375"
