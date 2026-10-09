from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.inventory import recipes
from app.modules.inventory.schemas import RecipeCreate
from app.modules.waitlist.originals import fingerprint
from test_purchase_orders_10l import setup
from test_stock_recipes_10c import payload
from test_inventory_outlook_10n import scenario
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


def exercise(client, engine, institute, service):
    with Session(engine) as db:
        serum, _, _ = setup(db, institute)
        original = recipes.create(db, institute, service, RecipeCreate(**payload(serum)), "manager")
        recipes.create(db, institute, service, RecipeCreate(**payload(serum, base_revision=1,
            entries=[{"item_id": serum, "quantity": "9.000"}], idempotency_key="revised")), "manager")
    def post(message, selection=None, role="accueil"):
        return client.post("/api/v1/copilot/query", headers=_auth_headers(role, institute),
            json={"message": message, "ui_context": selection or {}})
    read_message = "Consulter les stocks enregistres"
    forecast_message = "Projeter les besoins de stock du scenario"
    selected = {"scenario": scenario(service, original.id)}
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", collect)
    try:
        for message, ui, name in [(read_message, {}, "STOCK_READ"), (forecast_message, selected, "STOCK_FORECAST")]:
            response = post(message, ui)
            assert response.status_code == 200, response.text
            value = response.json()
            assert value["capability"] == name and value["actions"] == []
            evidence = value["evidence"]
            assert evidence["fingerprint"] == fingerprint({k: v for k, v in evidence.items() if k != "fingerprint"})
            result = evidence["result"]
            assert result["institute_id"] == institute and result["limit"] == 50
            assert '"actor_id"' not in response.text
            if name == "STOCK_FORECAST":
                assert result["coverage"] == "complete_selected_norms"
                assert result["demands"][0]["recipe_revision"] == 1
                assert next(row for row in result["items"] if row["item_id"] == serum)["known_demand"] == "12.375"
    finally:
        event.remove(engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}
    assert post(forecast_message).json()["status"] == "clarification"
    assert post(read_message, selected).status_code == 400
    assert post(read_message, role="collaboratrice").status_code == 403
    absent = post(forecast_message, {"scenario": scenario(service, None)}).json()["evidence"]["result"]
    assert absent["coverage"] == "partial_selected_norms"
    assert post(forecast_message, {"scenario": {**selected["scenario"], "starts_at": 1}}).status_code == 422


def test_sqlite_stock_and_pinned_forecast(client):
    institute, _, services = _bootstrap_reference_data(client)
    exercise(client, main_module.engine, institute, services[0]["id"])


def test_postgres_stock_and_pinned_forecast(client, postgres_flow, monkeypatch):
    engine, institute, _, service = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, engine, institute, service)
