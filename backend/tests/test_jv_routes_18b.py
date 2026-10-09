"""Signed fresh capture, isolation, fail-closed analysis and zero SQL mutations."""
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.base import upstream
from app.modules.jv.operational import OperationalAnalyzer
from app.modules.institutes.models import Institute
from app.modules.tickets.schemas import TicketCreate
from app.modules.tickets.service import create_queue_ticket
from app.modules.waitlist.originals import fingerprint
from test_base_query_17q import prepared, body, MESSAGES
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def post(client, institute, candidate, role="accueil"):
    return client.post("/api/v1/jv/query", json=candidate, headers=_auth_headers(role, institute))


def exercise(client, engine, institute, employee, ticket):
    with Session(engine) as db:
        owner = db.get(Institute, institute)
        db.add(Institute(id="jv-foreign", region_id=owner.region_id, name="Other", city="Other", timezone="Europe/Zurich"))
        db.commit()
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", collect)
    try:
        for name in MESSAGES:
            response = post(client, institute, body(name, employee, ticket))
            assert response.status_code == 200, response.text
            value = response.json(); source = value["source"]; analysis = value["analysis"]
            assert source["capability"] == analysis["capability"] == name
            assert source["evidence"]["institute_id"] == analysis["institute_id"] == institute
            assert analysis["evidence_fingerprint"] == source["evidence"]["fingerprint"]
            assert analysis["fingerprint"] == fingerprint({k: v for k, v in analysis.items() if k != "fingerprint"})
            assert source["actions"] == analysis["actions"] == []
        for name in ("EMPLOYEE_AVAILABILITY", "QUEUE_ASSIGNMENT_OPTIONS"):
            response = post(client, "jv-foreign", body(name, employee, ticket))
            assert response.status_code == 404 and employee not in response.text and ticket not in response.text
        response = post(client, "jv-foreign", body("QUEUE_READ", employee, ticket))
        assert response.status_code == 200
        assert response.json()["analysis"]["metrics"][0]["value"] == 0
    finally:
        event.remove(engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"}


def test_signed_sqlite_reads_produce_scoped_analysis_without_writes(client):
    institute, employee, ticket = prepared(client)
    exercise(client, main_module.engine, institute, employee, ticket)


def test_actual_postgres_signed_jv_capture_isolation_and_no_writes(client, postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    with Session(engine) as db:
        ticket = create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=service)).id
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, engine, institute, employee, ticket)


def test_auth_and_client_fact_injection_refused_before_framework(client, monkeypatch):
    institute, employee, ticket = prepared(client)
    def forbidden(*args): raise AssertionError("Must not route invalid authority")
    monkeypatch.setattr(upstream.OfficialRouter, "resolve", forbidden)
    candidate = body("QUEUE_READ", employee, ticket)
    assert client.post("/api/v1/jv/query", json=candidate).status_code == 403
    assert post(client, institute, candidate, "collaboratrice").status_code == 403
    for field in ("evidence", "analysis", "actor_id", "institute_id", "sql", "provider"):
        assert post(client, institute, {**candidate, field: "injected"}).status_code == 422


def test_clarification_does_not_invoke_jv(client, monkeypatch):
    institute, employee, ticket = prepared(client)
    def forbidden(*args): raise AssertionError("No facts to analyze")
    monkeypatch.setattr(OperationalAnalyzer, "analyze", forbidden)
    response = post(client, institute, {"message": MESSAGES["EMPLOYEE_AVAILABILITY"]})
    assert response.status_code == 200
    assert response.json()["source"]["status"] == "clarification" and response.json()["analysis"] is None


def test_framework_outage_and_invalid_analysis_source_fail_closed(client, monkeypatch):
    institute, employee, ticket = prepared(client)
    candidate = body("QUEUE_READ", employee, ticket)
    with monkeypatch.context() as scoped:
        def outage(*args): raise HTTPException(503, "BASE unavailable")
        scoped.setattr(upstream.OfficialRouter, "resolve", outage)
        assert post(client, institute, candidate).status_code == 503
    def invalid(*args): raise ValueError("private source detail")
    monkeypatch.setattr(OperationalAnalyzer, "analyze", invalid)
    response = post(client, institute, candidate)
    assert response.status_code == 503 and "private" not in response.text
