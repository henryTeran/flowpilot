from copy import deepcopy
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.base import read_capabilities as base
from app.modules.waitlist.originals import fingerprint
from app.modules.waitlist.models import DemandOriginal, LifecycleOriginal
from app.modules.optimizer.models import PolicyOriginal
from app.modules.institutes.models import Institute
from test_optimizer_sources_16d import prepare
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_waitlist_matching_15a import NOW


def prepared(client, monkeypatch):
    institute, employee, service, *_ = setup(client)
    request = prepare(main_module.engine, institute, employee, service, monkeypatch)
    monkeypatch.setattr(base, "utcnow", lambda: NOW)
    path = f"/api/v1/base/institutes/{institute}"
    invocations = [{"capability": "WAITLIST_READ", "arguments": {"root_id": request.root_id}},
        {"capability": "WAITLIST_MATCH", "arguments": {"root_id": request.root_id, "expected_event_id": request.expected_event_id,
            "expected_event_fingerprint": request.expected_event_fingerprint, "horizon_end": request.horizon_end.isoformat(), "policy": request.matching_policy.model_dump(mode="json")}},
        {"capability": "PLANNING_OPTIMIZATION", "arguments": request.model_dump(mode="json")}]
    return institute, path, invocations


def test_signed_discovery_context_and_reads_bind_server_actor_and_complete_proof(client, monkeypatch):
    institute, path, invocations = prepared(client, monkeypatch)
    headers = _auth_headers("responsable_institut", institute)
    discovery = client.get(path+"/capabilities", headers=headers)
    assert discovery.status_code == 200, discovery.text
    assert discovery.json()["principal"] == {"actor_id": "test-user", "institute_id": institute, "role": "responsable_institut"}
    assert [c["name"] for c in discovery.json()["capabilities"]] == [i["capability"] for i in invocations]
    with Session(main_module.engine) as db:
        models = (PolicyOriginal, DemandOriginal, LifecycleOriginal)
        counts = tuple(db.scalar(select(func.count()).select_from(m)) for m in models)
    for invocation in invocations:
        context = client.post(path+"/contexts/resolve", json=invocation, headers=headers)
        assert context.status_code == 200, context.text
        assert set(context.json()) == {"principal", "capability", "selected_arguments", "basis"}
        assert context.json()["basis"] == "authorized_selection_not_captured_business_facts"
        result = client.post(path+"/reads", json=invocation, headers=headers)
        assert result.status_code == 200, result.text
        value = result.json()
        assert value["fingerprint"] == fingerprint(value["evidence"])
        assert value["integrity"] == "full_response_sha256_not_retention_or_signature"
        assert value["evidence"]["context"] == context.json()
        assert value["evidence"]["context"]["principal"]["actor_id"] == "test-user"
        assert value["evidence"]["effect"] == "read_or_suggestion_only_no_booking_contact_or_external_execution"
        if invocation["capability"] == "WAITLIST_READ": assert value["evidence"]["result"]["state"] == "active"
        if invocation["capability"] == "WAITLIST_MATCH": assert value["evidence"]["result"]["review"]["options"]
        if invocation["capability"] == "PLANNING_OPTIMIZATION": assert value["evidence"]["result"]["review"]["ranking"] == "complete"
    with Session(main_module.engine) as db:
        assert tuple(db.scalar(select(func.count()).select_from(m)) for m in models) == counts


def test_signed_scope_roles_and_identity_injection_never_expand_read_capabilities(client, monkeypatch):
    institute, path, invocations = prepared(client, monkeypatch)
    body = invocations[0]
    for role, owner in [("accueil", institute), ("collaboratrice", institute), ("direction", institute), ("super_admin", institute), ("responsable_institut", "foreign")]:
        headers = _auth_headers(role, owner)
        discovery = client.get(path+"/capabilities", headers=headers)
        if role == "accueil": assert discovery.status_code == 200 and discovery.json()["capabilities"] == []
        else: assert discovery.status_code == 403
        for endpoint in ("/contexts/resolve", "/reads"):
            assert client.post(path+endpoint, headers=headers, json=body).status_code == 403
    assert client.get(path+"/capabilities").status_code == 403
    assert client.post(path+"/reads", json=body).status_code == 403
    headers = _auth_headers("responsable_institut", institute)
    for field in ("actor_id", "principal", "institute_id", "level", "approved", "sql", "captured_at", "score"):
        assert client.post(path+"/reads", headers=headers, json={**body, field: "injected"}).status_code == 422
    for capability in ("SQL_EXECUTE", "APPOINTMENT_CANCEL", "waitlist.lifecycle.read_state"):
        assert client.post(path+"/reads", headers=headers, json={**body, "capability": capability}).status_code == 422
    assert client.post(path+"/reads", headers=headers, json={**body, "arguments": {**body["arguments"], "sql": "SELECT * FROM customers"}}).status_code == 422


def test_context_resolution_does_not_load_business_data_and_read_preserves_refusal_stale_and_tenant_guards(client, monkeypatch):
    institute, path, invocations = prepared(client, monkeypatch)
    headers = _auth_headers("responsable_institut", institute)
    original = base.lifecycle.read_state
    def must_not_read(*args): raise AssertionError("Context cannot query business data")
    monkeypatch.setattr(base.lifecycle, "read_state", must_not_read)
    assert client.post(path+"/contexts/resolve", json=invocations[0], headers=headers).status_code == 200
    monkeypatch.setattr(base.lifecycle, "read_state", original)
    refused = deepcopy(invocations[1]); refused["arguments"]["policy"]["permission_requirement"] = "recorded_grant_required"
    response = client.post(path+"/reads", headers=headers, json=refused)
    assert response.status_code == 200
    assert response.json()["evidence"]["result"]["unavailable_reason"] == "permission_requirement_unmet"
    assert response.json()["fingerprint"] == fingerprint(response.json()["evidence"])
    for invocation in invocations[1:]:
        stale = deepcopy(invocation); stale["arguments"]["expected_event_fingerprint"] = "0"*64
        assert client.post(path+"/reads", headers=headers, json=stale).status_code == 400
    malformed = deepcopy(invocations[1]); malformed["arguments"]["horizon_end"] = "2026-10-09"
    assert client.post(path+"/reads", headers=headers, json=malformed).status_code == 422
    with Session(main_module.engine) as db:
        owner = db.get(Institute, institute)
        db.add(Institute(id="base-foreign", region_id=owner.region_id, name="Other institute", city=owner.city, timezone="Europe/Zurich")); db.commit()
    other = path.replace(institute, "base-foreign")
    assert client.post(other+"/reads", headers=_auth_headers("responsable_institut", "base-foreign"), json=invocations[0]).status_code == 404
