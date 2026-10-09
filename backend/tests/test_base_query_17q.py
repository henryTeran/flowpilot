"""Real official-framework -> signed API -> existing SQLite services, not a mock router."""
from copy import deepcopy
import hashlib
import pytest
from fastapi import HTTPException
from sqlalchemy import event, select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.base import query, query_routes, upstream
from app.modules.employees.models import Employee
from app.modules.institutes.models import Institute
from app.modules.waitlist.originals import fingerprint
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data, _create_ticket


MESSAGES = {
    "EMPLOYEE_AVAILABILITY": "Consulter la disponibilite des collaboratrices",
    "QUEUE_ASSIGNMENT_OPTIONS": "Qui peut prendre cette cliente maintenant",
    "QUEUE_READ": "Consulter la file operationnelle",
    "PLANNING_READ": "Consulter le planning du jour",
}


def prepared(client):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket = _create_ticket(client, institute, services[0]["id"])
    return institute, employees[0]["id"], ticket["id"]


def body(name, employee, ticket):
    ui = {"employee_id": employee} if name == "EMPLOYEE_AVAILABILITY" else {"ticket_id": ticket} if name == "QUEUE_ASSIGNMENT_OPTIONS" else {}
    return {"message": MESSAGES[name], "ui_context": ui}


def post(client, institute, candidate, role="accueil"):
    return client.post("/api/v1/base/query", json=candidate, headers=_auth_headers(role, institute))


def test_official_framework_four_services_read_only_and_minimal_evidence(client):
    institute, employee, ticket = prepared(client)
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(main_module.engine, "before_cursor_execute", collect)
    try:
        for name in MESSAGES:
            response = post(client, institute, body(name, employee, ticket))
            assert response.status_code == 200, response.text
            value = response.json()
            assert value["status"] == "answered" and value["capability"] == name
            assert value["framework"] == "ai-swiss/base@1.5.1" and value["actions"] == []
            evidence = value["evidence"]
            assert evidence["institute_id"] == institute
            assert evidence["effect"] == "read_or_suggest_only_no_mutation"
            assert evidence["fingerprint"] == fingerprint({k: v for k, v in evidence.items() if k != "fingerprint"})
            assert not any(field in response.text for field in ('"customer_id"', '"employee_name"', '"unit_price"', '"notes"', '"prompt"', '"message"'))
            if name == "EMPLOYEE_AVAILABILITY":
                assert evidence["result"]["employee_id"] == employee
            if name == "QUEUE_ASSIGNMENT_OPTIONS":
                assert evidence["result"]["options"]
                assert all(item["ticket_id"] == ticket for item in evidence["result"]["options"])
            if name == "QUEUE_READ":
                assert evidence["result"]["items"][0]["ticket_id"] == ticket
    finally:
        event.remove(main_module.engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "DROP", "CREATE"}


def test_unknown_and_missing_selection_never_query_business_data(client, monkeypatch):
    institute, employee, ticket = prepared(client)
    def forbidden(*args, **kwargs):
        raise AssertionError("Cannot dispatch unresolved intent")
    monkeypatch.setattr(query.scheduling, "availability_engine", forbidden)
    monkeypatch.setattr(query.assignment, "assignment_options_for_ticket", forbidden)
    monkeypatch.setattr(query.tickets, "read_operational_queue", forbidden)
    for candidate in [{"message": "xyzzy completely unknown"}, {"message": MESSAGES["EMPLOYEE_AVAILABILITY"]}, {"message": MESSAGES["QUEUE_ASSIGNMENT_OPTIONS"]}]:
        value = post(client, institute, candidate)
        assert value.status_code == 200, value.text
        assert value.json()["status"] == "clarification" and value.json()["evidence"] is None


def test_signed_permissions_and_injection_rejected_before_framework(client, monkeypatch):
    institute, employee, ticket = prepared(client)
    def forbidden(*args): raise AssertionError("Authorization first")
    monkeypatch.setattr(upstream.OfficialRouter, "resolve", forbidden)
    candidate = body("QUEUE_READ", employee, ticket)
    for role in ("collaboratrice", "direction", "super_admin"):
        assert post(client, institute, candidate, role).status_code == 403
    assert client.post("/api/v1/base/query", json=candidate).status_code == 403
    assert post(client, institute, {"message": "   "}).status_code == 422
    for field in ("institute_id", "actor_id", "capability", "sql", "approved", "provider"):
        assert post(client, institute, {**candidate, field: "injected"}).status_code == 422
        assert post(client, institute, {**candidate, "ui_context": {field: "injected"}}).status_code == 422


def test_foreign_employee_ticket_and_wrong_selection_never_leak(client):
    institute, employee, ticket = prepared(client)
    with Session(main_module.engine) as db:
        owner = db.get(Institute, institute)
        db.add(Institute(id="base-query-other", region_id=owner.region_id, name="Other", city=owner.city, timezone="Europe/Zurich"))
        db.commit()
    for name in ("EMPLOYEE_AVAILABILITY", "QUEUE_ASSIGNMENT_OPTIONS"):
        response = post(client, "base-query-other", body(name, employee, ticket))
        assert response.status_code == 404, response.text
        assert employee not in response.text and ticket not in response.text
    assert post(client, institute, {"message": MESSAGES["QUEUE_READ"], "ui_context": {"ticket_id": ticket}}).status_code == 400


def test_existing_assignment_guard_reservation_changes_options(client):
    institute, employee, ticket = prepared(client)
    # Reserve employee for a distinct queue ticket using the existing signed workflow.
    services = client.get("/api/v1/services/catalog").json()
    other = _create_ticket(client, institute, services[0]["id"])
    assigned = client.patch(f"/api/v1/tickets/{other['id']}/assign", json={"employee_id": employee}, headers=_auth_headers("accueil", institute))
    assert assigned.status_code == 200, assigned.text
    response = post(client, institute, body("QUEUE_ASSIGNMENT_OPTIONS", employee, ticket))
    assert response.status_code == 200, response.text
    option = next(item for item in response.json()["evidence"]["result"]["options"] if item["employee_id"] == employee)
    assert not option["assignable"] and option["reason"] == "employee_reserved"


def test_fake_provider_outage_invalid_output_and_bypass(client):
    institute, employee, ticket = prepared(client)
    calls = []
    class Fake:
        def propose(self, message, allowed):
            calls.append((message, allowed))
            return {"capability": "QUEUE_READ"}
    main_module.app.dependency_overrides[query_routes.provider] = lambda: Fake()
    response = post(client, institute, body("QUEUE_READ", employee, ticket))
    assert response.status_code == 200 and response.json()["status"] == "answered"
    assert calls == [(MESSAGES["QUEUE_READ"], tuple(query.REGISTRY))]
    class Offline:
        def propose(self, *args): raise RuntimeError("private provider outage")
    main_module.app.dependency_overrides[query_routes.provider] = lambda: Offline()
    response = post(client, institute, body("QUEUE_READ", employee, ticket))
    assert response.status_code == 200 and response.json()["status"] == "answered"
    class Bad:
        def propose(self, *args): return {"capability": "SQL_EXECUTE", "sql": "DELETE"}
    main_module.app.dependency_overrides[query_routes.provider] = lambda: Bad()
    response = post(client, institute, body("QUEUE_READ", employee, ticket))
    assert response.status_code == 502 and "DELETE" not in response.text
    main_module.app.dependency_overrides[query_routes.provider] = lambda: Fake()
    response = post(client, institute, {"message": "xyzzy completely unknown"})
    assert response.status_code == 200 and response.json()["status"] == "clarification"


def test_framework_failure_never_falls_back_to_independent_router(client, monkeypatch):
    institute, employee, ticket = prepared(client)
    def unavailable(*args): raise HTTPException(503, "BASE framework unavailable or invalid")
    monkeypatch.setattr(upstream.OfficialRouter, "resolve", unavailable)
    response = post(client, institute, body("QUEUE_READ", employee, ticket))
    assert response.status_code == 503


def test_unsafe_principal_and_unknown_capability_never_authorized():
    principal = query.identity.signed_principal({"sub": "actor", "institute_id": "own", "role": "accueil"}, "own")
    for changed in ({"institute_id": "foreign"}, {"role": "collaboratrice"}, {"actor_id": " bad "}):
        with pytest.raises(HTTPException): query.guard(principal.model_copy(update=changed), "own")
    with pytest.raises(TypeError): query.REGISTRY["SQL_EXECUTE"] = None


def test_registry_exposes_closed_real_schemas_and_existing_permissions(client):
    institute, employee, ticket = prepared(client)
    response = client.get("/api/v1/base/query-capabilities", headers=_auth_headers("accueil", institute))
    assert response.status_code == 200, response.text
    descriptors = response.json()
    assert [item["name"] for item in descriptors] == list(query.REGISTRY)
    for item in descriptors:
        assert item["input_schema"]["additionalProperties"] is False
        assert item["output_schema"]["additionalProperties"] is False
        assert item["mutates"] is False and item["level"] in (0, 1)
        assert item["permission"] == "can_manage_ticket_in_exact_signed_institute"
    assert list(query.ExecutionLevel) == [0, 1, 2, 3]
    assert client.get("/api/v1/base/query-capabilities", headers=_auth_headers("collaboratrice", institute)).status_code == 403


def test_availability_uses_real_engine_and_preserves_pause_guard(client, monkeypatch):
    institute, employee, ticket = prepared(client)
    with Session(main_module.engine) as db:
        row = db.get(Employee, employee)
        row.status = "pause"
        db.commit()
    original = query.scheduling.availability_engine
    calls = []
    def observed(db, institute_id, employee_id, service_id, now):
        calls.append((institute_id, employee_id, service_id))
        return original(db, institute_id, employee_id, service_id, now=now)
    monkeypatch.setattr(query.scheduling, "availability_engine", observed)
    response = post(client, institute, body("EMPLOYEE_AVAILABILITY", employee, ticket))
    assert response.status_code == 200, response.text
    assert calls == [(institute, employee, None)]
    result = response.json()["evidence"]["result"]
    assert not result["available"] and result["current_slot"]["reason"] == "employee_pause"
    assert result["current_slot"]["available_from"] is None


def test_runtime_bridge_timeout_and_malformed_result_fail_closed(monkeypatch):
    import subprocess
    def timeout(*args, **kwargs):
        assert args[0][0] == "node" and "shell" not in kwargs
        assert kwargs["timeout"] == 15
        assert "private" not in " ".join(args[0])
        raise subprocess.TimeoutExpired(args[0], 15)
    monkeypatch.setattr(upstream.subprocess, "run", timeout)
    with pytest.raises(HTTPException) as error:
        upstream.OfficialRouter().resolve("private")
    assert error.value.status_code == 503
    def corrupt(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout='{"status":"routed","sql":"DELETE"}')
    monkeypatch.setattr(upstream.subprocess, "run", corrupt)
    with pytest.raises(HTTPException) as error:
        upstream.OfficialRouter().resolve("private")
    assert error.value.status_code == 503 and "DELETE" not in error.value.detail


def test_unicode_message_size_matches_python_and_node_contract(client):
    institute, employee, ticket = prepared(client)
    # Python counts Unicode codepoints; JS string.length counts UTF-16 units.
    response = post(client, institute, {"message": "🙂" * 2000})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "clarification" and response.json()["evidence"] is None
