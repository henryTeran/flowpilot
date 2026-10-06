import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import app.main as main_module
from app.core.security import create_access_token
from app.modules.inventory import recipes, service
from app.modules.inventory.models import StockRecipe, StockRecipeLine
from app.modules.inventory.schemas import ItemCreate, RecipeCreate
from app.modules.institutes.models import Institute
from test_inventory_10a import item
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow, race


def payload(item_id, **changes):
    return {**dict(base_revision=0, enabled=True, entries=[dict(item_id=item_id, quantity="4.125")],
        reason="Norme approuvee", idempotency_key="recipe-original"), **changes}


def test_recipe_original_replay_survives_later_revision_and_disable(client):
    institute, _, services = _bootstrap_reference_data(client)
    manager = _auth_headers("responsable_institut", institute)
    operator = _auth_headers(institute_id=institute)
    base = f"/api/v1/inventory/institutes/{institute}"
    stock = client.post(base + "/items", headers=manager, json=item()).json()
    path = base + f"/services/{services[0]['id']}"
    assert client.get(path + "/recipe", headers=operator).json() is None
    created = client.post(path + "/recipes", headers=manager, json=payload(stock["id"]))
    assert created.status_code == 200
    original = created.json()
    assert original["entries"] == [dict(item_id=stock["id"], quantity="4.125", unit="ml")]
    assert original["revision"] == 1 and original["base_revision"] == 0
    assert original["actor_id"] == "test-user"
    assert client.get(path + "/recipe", headers=operator).json() == original
    assert client.post(base + f"/services/{services[1]['id']}/recipes", headers=manager,
                       json=payload(stock["id"])).status_code == 400
    newer = payload(stock["id"], base_revision=1, entries=[dict(item_id=stock["id"], quantity="8.25")], idempotency_key="new-version")
    second = client.post(path + "/recipes", headers=manager, json=newer).json()
    assert second["revision"] == 2 and second["entries"][0]["quantity"] == "8.250"
    assert client.post(path + "/recipes", headers=manager, json=payload(stock["id"])).json() == original
    assert client.get(base + f"/recipes/{original['id']}", headers=operator).json() == original
    assert client.post(path + "/recipes", headers=manager, json=payload(stock["id"], idempotency_key="stale")).status_code == 400
    disabled = payload(stock["id"], base_revision=2, enabled=False, entries=[], idempotency_key="disable")
    third = client.post(path + "/recipes", headers=manager, json=disabled).json()
    assert third["revision"] == 3 and third["entries"] == [] and third["enabled"] is False
    assert client.get(path + "/recipe", headers=operator).json() == third
    assert client.post(path + "/recipes", headers=manager, json=newer).json() == second
    history = client.get(path + "/recipes?limit=2", headers=operator).json()
    assert [row["revision"] for row in history] == [3, 2]
    assert client.get(base + f"/items/{stock['id']}", headers=operator).json()["on_hand"] == "0.000"
    for changed in (payload(stock["id"], reason="Other reason"), payload(stock["id"], base_revision=1), payload(stock["id"], entries=[dict(item_id=stock["id"], quantity="4.126")])):
        assert client.post(path + "/recipes", headers=manager, json=changed).status_code == 400
    other = {"Authorization": "Bearer " + create_access_token(subject="other", extra_claims={"role": "responsable_institut", "institute_id": institute})}
    assert client.post(path + "/recipes", headers=other, json=payload(stock["id"])).status_code == 400


def test_recipe_roles_units_foreign_items_and_duplicates_are_refused(client):
    institute, _, services = _bootstrap_reference_data(client)
    manager = _auth_headers("responsable_institut", institute)
    base = f"/api/v1/inventory/institutes/{institute}"
    stock = client.post(base + "/items", headers=manager, json=item(unit="unit", reorder_threshold="1")).json()
    path = base + f"/services/{services[0]['id']}/recipes"
    for headers in ({}, _auth_headers(institute_id=institute), _auth_headers("responsable_institut", None), _auth_headers("responsable_institut", "foreign")):
        assert client.post(path, headers=headers, json=payload(stock["id"])).status_code == 403
    assert client.post(path, headers=manager, json=payload(stock["id"])).status_code == 400
    entries = [dict(item_id=stock["id"], quantity="1")]
    for changed in (dict(entries=[]), dict(enabled=False), dict(entries=entries * 2), dict(base_revision=True), dict(enabled="true"), dict(entries=[dict(item_id=stock["id"], quantity="0")])):
        assert client.post(path, headers=manager, json=payload(stock["id"], **changed)).status_code == 422
    with Session(main_module.engine) as db:
        original = db.get(Institute, institute)
        db.add(Institute(id="recipe-other", region_id=original.region_id, name="Other", city="Other", timezone=original.timezone, status="active"))
        db.commit()
        foreign = service.create_item(db, "recipe-other", ItemCreate(**item()), "manager")
    assert client.post(path, headers=manager, json=payload(foreign.id)).status_code == 404
    assert client.post(base + "/services/missing/recipes", headers=manager, json=payload(stock["id"], entries=entries)).status_code == 404
    created = client.post(path, headers=manager, json=payload(stock["id"], entries=entries)).json()
    foreign_base = "/api/v1/inventory/institutes/recipe-other"
    assert client.get(foreign_base + f"/recipes/{created['id']}", headers=_auth_headers("responsable_institut", "recipe-other")).status_code == 404
    assert client.get(base + f"/recipes/{created['id']}", headers=_auth_headers("responsable_institut", "recipe-other")).status_code == 403


def test_recipe_lines_and_header_commit_atomically_and_entry_order_is_not_identity(client):
    institute, _, services = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        first = service.create_item(db, institute, ItemCreate(**item()), "manager")
        second = service.create_item(db, institute, ItemCreate(**item(sku="SECOND", idempotency_key="second")), "manager")
        data = RecipeCreate(**payload(first.id, entries=[dict(item_id=first.id, quantity="1.125"), dict(item_id=second.id, quantity="2.125")]))
        def fail(db, context, instances):
            if any(isinstance(row, StockRecipeLine) for row in db.new):
                raise RuntimeError("Injected recipe line failure")
        event.listen(Session, "before_flush", fail)
        try:
            with pytest.raises(RuntimeError, match="Injected recipe"):
                recipes.create(db, institute, services[0]["id"], data, "manager")
            db.rollback()
        finally:
            event.remove(Session, "before_flush", fail)
        assert list(db.scalars(select(StockRecipe))) == []
        assert list(db.scalars(select(StockRecipeLine))) == []
        original = recipes.create(db, institute, services[0]["id"], data, "manager")
        reversed_data = data.model_copy(update={"entries": list(reversed(data.entries))})
        assert recipes.create(db, institute, services[0]["id"], reversed_data, "manager") == original
        assert original.revision == 1


def test_postgres_recipe_replay_and_concurrent_revision_guard(postgres_flow):
    engine, institute, _, care = postgres_flow
    with Session(engine) as db:
        stock = service.create_item(db, institute, ItemCreate(**item()), "manager")
    data = RecipeCreate(**payload(stock.id))
    result = race(engine, [lambda db: recipes.create(db, institute, care, data, "manager")] * 2)
    assert all(row[0] == "ok" for row in result) and result[0][1] == result[1][1]
    update = RecipeCreate(**payload(stock.id, base_revision=1, idempotency_key="update"))
    disable = RecipeCreate(**payload(stock.id, base_revision=1, enabled=False, entries=[], idempotency_key="disable"))
    result = race(engine, [lambda db: recipes.create(db, institute, care, update, "manager"), lambda db: recipes.create(db, institute, care, disable, "manager")])
    assert sorted(row[0] for row in result) == ["conflict", "ok"]
    with Session(engine) as db:
        assert recipes.current(db, institute, care).revision == 2
        assert len(list(db.scalars(select(StockRecipe)))) == 2


def test_postgres_recipe_line_owner_constraints(postgres_flow):
    engine, institute, _, care = postgres_flow
    with Session(engine) as db:
        stock = service.create_item(db, institute, ItemCreate(**item()), "manager")
        recipe = recipes.create(db, institute, care, RecipeCreate(**payload(stock.id)), "manager")
        original = db.get(Institute, institute)
        db.add(Institute(id="recipe-other", region_id=original.region_id, name="Other", city="Other", timezone=original.timezone, status="active"))
        db.commit()
        other_stock = service.create_item(db, "recipe-other", ItemCreate(**item()), "manager")
        other_recipe = recipes.create(db, "recipe-other", care, RecipeCreate(**payload(other_stock.id, enabled=False, entries=[])), "manager")
        for recipe_id, item_id in ((other_recipe.id, stock.id), (recipe.id, other_stock.id)):
            db.add(StockRecipeLine(recipe_id=recipe_id, item_id=item_id, institute_id="recipe-other", quantity_milli=1000, unit="ml"))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
