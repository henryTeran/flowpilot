from datetime import datetime
import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.copilot import query, opportunities
from app.modules.revenue import rebooking
from app.modules.waitlist.originals import fingerprint
from test_revenue_rebooking_14e import exercise as seed
from test_postgres_scheduling_4d import postgres_flow
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers


def exercise(client, engine, institute, employee, service, monkeypatch):
    seed(engine, institute, employee, service, monkeypatch)
    def post(ui=None, role="responsable_institut", owner=institute):
        return client.post("/api/v1/copilot/query", headers=_auth_headers(role, owner),
            json={"message": "Examiner les opportunites de revenus",
                  "ui_context": {"opportunity_source": "rebooking"} if ui is None else ui})
    with Session(engine) as db:
        original = rebooking.read(db, institute)
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", collect)
    try:
        response = post()
        assert response.status_code == 200, response.text
        data = response.json()
        evidence, result = data["evidence"], data["evidence"]["result"]
        assert data["capability"] == "REVENUE_OPPORTUNITIES" and data["actions"] == []
        assert result["total_candidates"] == 23 and len(result["candidates"]) == 20
        assert result["source_digest"] == fingerprint(original.model_dump(mode="json"))
        assert result["already_booked_customers"] == 1
        assert result["diagnostics"]["care_invalid_actual_times"] == 1
        assert datetime.fromisoformat(evidence["captured_at"]) == original.captured_at
        assert evidence["fingerprint"] == fingerprint({k: v for k, v in evidence.items() if k != "fingerprint"})
        assert result["estimated_value"] is None and not result["action_executed"] and not result["delivery_authorized"]
        for name in ("phone", "birthday", "created_by", "communication", "lifecycle_original", "display_name"):
            assert name not in response.text
        assert all(row["rule"]["trigger"] == "rebooking" and row["state"] == "due" for row in result["candidates"])
        assert "rebook-00" not in {row["customer_id"] for row in result["candidates"]}
    finally:
        event.remove(engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}
    assert post(role="accueil").status_code == 403
    assert post(owner="foreign").status_code == 404
    assert post({"opportunity_source": "rebooking", "service_id": service}).status_code == 400
    assert post({"opportunity_source": "rebooking", "customer_id": "injected"}).status_code == 400
    assert post({"opportunity_source": "invented"}).status_code == 422
    assert post({}).json()["status"] == "clarification"
    with pytest.raises(ValueError):
        opportunities.Returns.model_validate({**result, "institute_id": "foreign"})
    with pytest.raises(ValueError):
        opportunities.Returns.model_validate({**result, "total_candidates": 0})


def test_sqlite_signed_rebooking_opportunities(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    exercise(client, main_module.engine, institute, employee, service, monkeypatch)


def test_postgres_signed_rebooking_opportunities(client, postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, engine, institute, employee, service, monkeypatch)


def test_discovery_source_selection_contract():
    schema = query.REGISTRY["REVENUE_OPPORTUNITIES"].input_schema
    assert len(schema["oneOf"]) == 3
    query.OpportunitySelection(opportunity_source="rebooking")
    for values in ({}, {"opportunity_source": "rebooking", "service_id": "injected"}):
        with pytest.raises(ValueError):
            query.OpportunitySelection.model_validate(values)
