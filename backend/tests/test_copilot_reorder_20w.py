from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import event, select, func
from sqlalchemy.orm import Session
from fastapi import HTTPException
import app.main as main
from app.database.session import get_db
from app.modules.inventory import reorders, orders, outlook, recipes, service as stock
from app.modules.inventory.models import StockPurchaseOrder, StockMovement, StockReorderOriginal
from app.modules.inventory.order_schemas import OrderCreate, ReceiptCreate
from app.modules.inventory.schemas import RecipeCreate, ItemCreate
from app.modules.waitlist.originals import fingerprint
from test_purchase_orders_10l import setup, reception
from test_stock_recipes_10c import payload as recipe_payload
from test_inventory_10a import item as item_terms
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from app.shared.time import utcnow


def exercise(client, engine, institute, service, monkeypatch):
    now = utcnow()
    with Session(engine) as db:
        serum, cartridge, terms = setup(db, institute)
        order = orders.create(db, institute, OrderCreate(**terms), "private-supplier-actor")
        recipe = recipes.create(db, institute, service, RecipeCreate(**recipe_payload(serum)), "manager")
        recipe_id = recipe.id
        for index in range(51):
            stock.create_item(db,institute,ItemCreate(**item_terms(sku=f"A{index:03}",idempotency_key=f"other-{index}")),"manager")
        assert serum not in {row.item_id for row in outlook.read(db,institute,50,0).items}
    selection = dict(supplier_id=terms["supplier_id"], item_ids=[serum, cartridge], pending_order_assumption="ignore_pending_orders")
    request = dict(message="Preparer une proposition de reapprovisionnement", ui_context=selection)
    headers = _auth_headers("responsable_institut", institute)
    path = "/api/v1/copilot"
    def preview(value=request, role="responsable_institut", owner=institute):
        return client.post(path+"/prepare-preview/reorder", headers=_auth_headers(role,owner), json=value)
    statements = []
    def observe(conn,cursor,statement,parameters,context,executemany):statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine,"before_cursor_execute",observe)
    try:
        response = preview()
        assert response.status_code == 200, response.text
        first = response.json()
        assert first["coverage"] == "not_applicable"
        items = {item["item_id"]:item for item in first["items"]}
        assert set(items) == {serum,cartridge}  # explicit scope includes an article beyond the first catalogue page
        assert items[serum]["proposed_quantity"] == "4.125" and items[cartridge]["proposed_quantity"] == "1.000"
        assert items[serum]["complete_demand"] is None
        assert "private-supplier-actor" not in response.text and '"supplier_name"' not in response.text
        conditional = preview({**request,"ui_context":{**selection,"pending_order_assumption":"all_pending_orders_received"}})
        assert conditional.status_code == 200
        assert all(item["proposed_quantity"] == "0.000" for item in conditional.json()["items"])
        scenario = dict(starts_at=now.isoformat(), ends_at=(now+timedelta(days=1)).isoformat(),
            demands=[dict(service_id=service,recipe_id=recipe_id,quantity=3)])
        projected = preview({**request,"ui_context":{**selection,"scenario":scenario}})
        assert projected.status_code == 200, projected.text
        assert projected.json()["coverage"] == "complete_selected_norms"
        observed = next(item for item in projected.json()["items"] if item["item_id"] == serum)
        assert observed["known_demand"] == "12.375" and observed["proposed_quantity"] == "16.500"
        missing = {**scenario,"demands":[dict(service_id=service,recipe_id=None,quantity=3)]}
        partial = preview({**request,"ui_context":{**selection,"scenario":missing}}).json()
        assert partial["coverage"] == "partial_selected_norms" and all(item["complete_demand"] is None for item in partial["items"])
    finally:event.remove(engine,"before_cursor_execute",observe)
    assert not set(statements) & {"INSERT","UPDATE","DELETE"}
    body = dict(message=request["message"], proposal=dict(selection=selection,expected_state_fingerprint=first["state_fingerprint"],
        reason="Reviewed exact reorder",idempotency_key="reorder-retained"))
    def prepare(value=body):return client.post(path+"/prepare/reorder",headers=headers,json=value)
    assert preview(role="accueil").status_code == 403
    assert preview(owner="foreign").status_code == 404
    assert preview({**request,"message":"Preparer un brouillon de campagne marketing"}).status_code == 400
    for change in ({"item_ids":[serum,serum]}, {"item_ids":[]}, {"supplier_id":" padded "}, {"pending_order_assumption":True}):
        assert preview({**request,"ui_context":{**selection,**change}}).status_code == 422
    assert prepare({**body,"proposal":{**body["proposal"],"expected_state_fingerprint":"0"*64}}).status_code == 400
    source_reader = outlook.item_rows
    def contradictory_source(*args,**kwargs):
        return [row.model_copy(update={"threshold":"1.125"}) if row.item_id==cartridge else row for row in source_reader(*args,**kwargs)]
    with monkeypatch.context() as patch:
        patch.setattr(outlook,"item_rows",contradictory_source)
        assert preview().status_code == 400  # defensive reader contract: fractional whole-unit projection
    result = prepare()
    assert result.status_code == 200, result.text
    retained = result.json()
    assert retained["fingerprint"] == fingerprint(retained["original"])
    assert retained["original"]["actor_id"] == "test-user"
    identifier = retained["original"]["id"]
    assert client.get(path+"/reorder-proposals/"+identifier,headers=headers).json() == retained
    assert client.get(path+"/reorder-proposal-by-key",params={"key":body["proposal"]["idempotency_key"]},headers=headers).json() == retained
    absent = client.get(path+"/reorder-proposal-by-key",params={"key":"absent-reorder-key"},headers=headers)
    assert absent.status_code == 200 and absent.json() is None
    foreign = client.get(path+"/reorder-proposal-by-key",params={"key":body["proposal"]["idempotency_key"]},headers=_auth_headers("responsable_institut","foreign"))
    assert foreign.status_code == 404  # the selected foreign institute does not exist
    assert client.get(path+"/reorder-proposal-by-key",params={"key":" invalid "},headers=headers).status_code == 400
    assert client.get(path+"/reorder-proposal-by-key",params={"key":"absent"},headers=_auth_headers("accueil",institute)).status_code == 403
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(StockPurchaseOrder)) == 1
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 0
        orders.receive(db,institute,order.id,ReceiptCreate(**reception(serum)),"physical-receiver")
    assert prepare().json() == retained  # historical projection, no new order/receipt
    assert prepare({**body,"proposal":{**body["proposal"],"idempotency_key":"new-key"}}).status_code == 400
    assert prepare({**body,"proposal":{**body["proposal"],"reason":"Changed reason"}}).status_code == 400
    assert client.get(path+"/reorder-proposals/"+identifier,headers=_auth_headers("responsable_institut","foreign")).status_code == 404
    capability = next(row for row in client.get(path+"/preparation-capabilities",headers=headers).json() if row["name"]=="STOCK_REORDER_PROPOSAL")
    assert capability["level"] == 2
    assert capability["output_schema"]["$defs"]["Original"]["additionalProperties"] is False


def test_sqlite_reorder_proposal(client,monkeypatch):
    institute,_,services = _bootstrap_reference_data(client)
    exercise(client,main.engine,institute,services[0]["id"],monkeypatch)


def test_postgres_reorder_proposal(client,postgres_flow,monkeypatch):
    engine,institute,_,service = postgres_flow
    def database():
        with Session(engine) as db:yield db
    main.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main,"engine",engine)
    exercise(client,engine,institute,service,monkeypatch)


def test_postgres_reorder_race_rollback_integrity_and_historical_recovery(postgres_flow,monkeypatch):
    engine,institute = postgres_flow[:2]
    with Session(engine) as db:
        serum,_,terms = setup(db,institute)
        selection = reorders.Selection(supplier_id=terms["supplier_id"],item_ids=(serum,),pending_order_assumption="ignore_pending_orders")
        preview = reorders.preview(db,institute,selection)
        request = reorders.Request(selection=selection,expected_state_fingerprint=preview.state_fingerprint,reason="Reviewed exact reorder",idempotency_key="race")
        db.rollback()
    def run():
        with Session(engine) as db:return reorders.create(db,institute,request,"manager")
    with ThreadPoolExecutor(max_workers=2) as pool:
        one,two = [future.result(timeout=20) for future in [pool.submit(run),pool.submit(run)]]
    assert one == two
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(StockReorderOriginal)) == 1
        def fail(session,context,instances):
            if any(isinstance(row,StockReorderOriginal) for row in session.new):raise RuntimeError("Injected reorder failure")
        event.listen(db,"before_flush",fail)
        try:
            with pytest.raises(RuntimeError):reorders.create(db,institute,request.model_copy(update={"idempotency_key":"rollback"}),"manager")
        finally:event.remove(db,"before_flush",fail)
        assert db.scalar(select(func.count()).select_from(StockReorderOriginal)) == 1
        row = db.get(StockReorderOriginal,one.original["id"])
        original = row.original
        row.original = {**original,"actor_id":"tampered"}
        row.fingerprint = fingerprint(row.original)
        db.commit()
        with pytest.raises(HTTPException):reorders.require(db,institute,row.id)
        row.original, row.fingerprint = original, one.fingerprint
        db.commit()
        def no_preview(*args,**kwargs):raise AssertionError("Historical proposal recaptured sources")
        monkeypatch.setattr(reorders,"preview",no_preview)
        assert reorders.create(db,institute,request,"manager") == one
