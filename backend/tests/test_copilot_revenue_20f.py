from datetime import timedelta
from decimal import Decimal
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.waitlist.originals import fingerprint
from app.modules.institutes.models import Institute
from app.modules.tickets.models import QueueTicket
from test_revenue_sources_14a import exercise as seed
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


def exercise(client, engine, institute, service, monkeypatch):
    original = seed(engine, institute, service, monkeypatch)
    with Session(engine) as db:
        db.add(Institute(id="revenue_copilot_foreign", region_id=db.get(Institute, institute).region_id, name="Other", city="Other"))
        db.flush()
        db.add(QueueTicket(id="foreign_revenue", institute_id="revenue_copilot_foreign", ticket_number="Private",
            status="paid", arrival_time=original.window.start,
            paid_at=original.window.end-timedelta(hours=1), currency="CHF", total_amount=Decimal("9999.99")))
        db.commit()
    ui = {"start": original.window.start.isoformat(), "end": original.window.end.isoformat()}
    def post(selection=ui, role="responsable_institut"):
        return client.post("/api/v1/copilot/query", headers=_auth_headers(role, institute),
            json={"message": "Consulter le resume des revenus enregistres", "ui_context": selection})
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", collect)
    try:
        response = post()
        assert response.status_code == 200, response.text
        value = response.json()
        assert value["capability"] == "REVENUE_SUMMARY" and value["actions"] == []
        evidence = value["evidence"]
        assert evidence["result"] == original.model_dump(mode="json")
        assert evidence["fingerprint"] == fingerprint({k: v for k, v in evidence.items() if k != "fingerprint"})
        assert '"customer_id"' not in response.text and '"ticket_id"' not in response.text
        assert "Private" not in response.text and "999999" not in response.text
    finally:
        event.remove(engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}
    assert post(role="accueil").status_code == 403
    assert post({}).json()["status"] == "clarification"
    assert post({**ui, "start": 1}).status_code == 422
    assert post({**ui, "end": original.window.start.isoformat()}).status_code == 400
    assert post({**ui, "end": (original.window.captured_at+timedelta(days=1)).isoformat()}).status_code == 400
    assert post({**ui, "customer_id": "injected"}).status_code == 400


def test_sqlite_recorded_revenue_summary(client, monkeypatch):
    institute, _, services = _bootstrap_reference_data(client)
    exercise(client, main_module.engine, institute, services[0]["id"], monkeypatch)


def test_postgres_recorded_revenue_summary(client, postgres_flow, monkeypatch):
    engine, institute, _, service = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, engine, institute, service, monkeypatch)
