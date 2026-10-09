"""Actual PostgreSQL + official BASE + signed HTTP reads in owned random schemas."""
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.institutes.models import Institute
from app.modules.tickets.schemas import TicketCreate
from app.modules.tickets.service import create_queue_ticket
from app.modules.waitlist.originals import fingerprint
from test_postgres_scheduling_4d import postgres_flow
from test_base_query_17q import MESSAGES, body, post


def test_actual_postgres_official_base_reads_tenant_isolation_and_no_mutation(client, postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    with Session(engine) as db:
        ticket = create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=service)).id
        owner = db.get(Institute, institute)
        db.add(Institute(id="base-pg-foreign", region_id=owner.region_id, name="Other", city=owner.city, timezone="Europe/Zurich"))
        db.commit()
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", collect)
    try:
        for name in MESSAGES:
            response = post(client, institute, body(name, employee, ticket), role="responsable_institut")
            assert response.status_code == 200, response.text
            value = response.json()
            assert value["status"] == "answered" and value["capability"] == name
            assert value["framework"] == "ai-swiss/base@1.5.1" and value["actions"] == []
            evidence = value["evidence"]
            assert evidence["institute_id"] == institute
            assert evidence["fingerprint"] == fingerprint({k: v for k, v in evidence.items() if k != "fingerprint"})
        for name in ("EMPLOYEE_AVAILABILITY", "QUEUE_ASSIGNMENT_OPTIONS"):
            foreign = post(client, "base-pg-foreign", body(name, employee, ticket))
            assert foreign.status_code == 404
            assert employee not in foreign.text and ticket not in foreign.text
        empty = post(client, "base-pg-foreign", body("QUEUE_READ", employee, ticket))
        assert empty.status_code == 200 and empty.json()["evidence"]["result"]["items"] == []
    finally:
        event.remove(engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "DROP", "CREATE"}
