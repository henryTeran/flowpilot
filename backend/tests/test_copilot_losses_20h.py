from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.waitlist.originals import fingerprint
from test_revenue_closures_14c import exercise as booking_sources
from test_revenue_walk_in_cancellations_14h import exercise as walk_in_sources
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


def exercise(client, engine, institute, employee, service, monkeypatch):
    bookings = booking_sources(engine, institute, employee, service, monkeypatch)
    walk_ins = walk_in_sources(engine, institute, service, monkeypatch)
    ui = {"start": bookings.window.start.isoformat(), "end": bookings.window.end.isoformat()}
    def post(selection=ui, role="responsable_institut"):
        return client.post("/api/v1/copilot/query", headers=_auth_headers(role, institute),
            json={"message": "Examiner les pertes de revenus enregistrees", "ui_context": selection})
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", collect)
    try:
        response = post()
        assert response.status_code == 200, response.text
        value = response.json()
        evidence = value["evidence"]
        result = evidence["result"]
        assert value["capability"] == "REVENUE_LOSS_ANALYSIS" and value["actions"] == []
        assert result["bookings"]["cancelled_count"] == 13 and result["bookings"]["no_show_count"] == 12
        assert result["walk_ins"]["retained_terms_count"] == 25 and result["walk_ins"]["legacy_unpriced_count"] == 1
        assert result["bookings"]["source_digest"] == fingerprint(bookings.model_dump(mode="json"))
        assert result["walk_ins"]["source_digest"] == fingerprint(walk_ins.model_dump(mode="json"))
        assert result["walk_ins"]["retained_amounts"] == walk_ins.model_dump(mode="json")["retained_amounts"]
        assert result["financial_loss"] is None and not result["causal_loss_proven"]
        assert evidence["fingerprint"] == fingerprint({k: v for k, v in evidence.items() if k != "fingerprint"})
        assert all(field not in response.text for field in ('"customer_id"', '"actor_id"', '"ticket_id"', '"opportunities"'))
    finally:
        event.remove(engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}
    assert post(role="accueil").status_code == 403
    assert post({}).json()["status"] == "clarification"
    assert post({**ui, "start": 1}).status_code == 422
    assert post({**ui, "end": ui["start"]}).status_code == 400
    assert post({**ui, "customer_id": "injected"}).status_code == 400


def test_sqlite_loss_sources(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise(client, main_module.engine, institute, employees[0]["id"], services[0]["id"], monkeypatch)


def test_postgres_loss_sources(client, postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, engine, institute, employee, service, monkeypatch)
