from copy import deepcopy
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.base import read_capabilities as base
from app.modules.optimizer.models import PolicyOriginal
from app.modules.waitlist.models import DemandOriginal, LifecycleOriginal
from test_optimizer_sources_16d import prepare
from test_workforce_absences_11b import setup
from test_postgres_scheduling_4d import postgres_flow
from test_waitlist_matching_15a import NOW


def principal(institute="own", role="responsable_institut"):
    return base.signed_principal({"sub": "signed-manager", "institute_id": institute, "role": role}, institute)


def test_registry_is_closed_minimal_and_scoped_with_no_execution_or_dynamic_tool_metadata():
    assert [c.name for c in base.capabilities(principal(), "own")] == ["WAITLIST_READ", "WAITLIST_MATCH", "PLANNING_OPTIMIZATION"]
    assert [c.level for c in base.capabilities(principal(), "own")] == [0, 1, 1]
    assert all(c.mutates is False and c.external_execution is False for c in base.REGISTRY.values())
    with pytest.raises(TypeError): base.REGISTRY["SQL_EXECUTE"] = None
    for role in ("accueil", "collaboratrice", "direction", "super_admin"):
        assert base.capabilities(principal(role=role), "own") == ()
        with pytest.raises(HTTPException) as error: base.authorize(principal(role=role), "own", "WAITLIST_READ")
        assert error.value.status_code == 403
    with pytest.raises(HTTPException): base.capabilities(principal(), "foreign")
    with pytest.raises(HTTPException): base.authorize(principal(), "own", "SQL_EXECUTE")


@pytest.mark.parametrize("change", [{"sub": None}, {"sub": " actor "}, {"sub": "bad\nactor"}, {"sub": 1},
    {"institute_id": None}, {"institute_id": "foreign"}, {"role": "unregistered"}])
def test_signed_scope_requires_exact_server_claims(change):
    with pytest.raises(HTTPException) as error:
        base.signed_principal({"sub": "signed-manager", "institute_id": "own", "role": "responsable_institut", **change}, "own")
    assert error.value.status_code == 403


def test_candidate_injection_unknown_tools_and_unsafe_model_copies_never_dispatch(monkeypatch):
    calls = []
    monkeypatch.setattr(base.lifecycle, "read_state", lambda *args: calls.append(args))
    valid = {"capability": "WAITLIST_READ", "arguments": {"root_id": "selected"}}
    for candidate in [{**valid, "actor_id": "injected"}, {**valid, "institute_id": "foreign"}, {**valid, "level": 3},
        {**valid, "capability": "APPOINTMENT_CANCEL"}, {**valid, "capability": "waitlist.lifecycle.read_state"},
        {**valid, "arguments": {"root_id": "selected", "sql": "DELETE FROM tickets"}}, {**valid, "arguments": {"root_id": 1}}]:
        with pytest.raises(HTTPException): base.invoke(None, principal(), "own", candidate)
    invalid = base.ReadInvocation.model_validate(valid).model_copy(update={"arguments": {"root_id": "selected", "approved": True}})
    with pytest.raises(HTTPException): base.invoke(None, principal(), "own", invalid)
    for changed in [{"role": "accueil"}, {"role": "unknown"}, {"institute_id": "foreign"}, {"actor_id": " bad "}]:
        with pytest.raises(HTTPException): base.invoke(None, principal().model_copy(update=changed), "own", valid)
    assert calls == []


def exercise(engine, institute, employee, service, monkeypatch):
    request = prepare(engine, institute, employee, service, monkeypatch)
    monkeypatch.setattr(base, "utcnow", lambda: NOW)
    user = principal(institute)
    read = {"capability": "WAITLIST_READ", "arguments": {"root_id": request.root_id}}
    match = {"capability": "WAITLIST_MATCH", "arguments": {"root_id": request.root_id, "expected_event_id": request.expected_event_id,
        "expected_event_fingerprint": request.expected_event_fingerprint, "horizon_end": request.horizon_end, "policy": request.matching_policy.model_dump()}}
    optimize = {"capability": "PLANNING_OPTIMIZATION", "arguments": request.model_dump()}
    with Session(engine) as db:
        models = (PolicyOriginal, DemandOriginal, LifecycleOriginal)
        counts = tuple(db.scalar(select(func.count()).select_from(m)) for m in models)
        state = base.invoke(db, user, institute, read)
        assert state.result.state == "active" and state.result.root.original["id"] == request.root_id
        assert state.context.selected_arguments == {"root_id": request.root_id}
        assert state.context.basis == "authorized_selection_not_captured_business_facts"
        matching = base.invoke(db, user, institute, match)
        assert matching.result.review.options and matching.result.captured_at == NOW
        scored = base.invoke(db, user, institute, optimize)
        assert scored.result.review.ranking == "complete"
        assert scored.result.policy_original.fingerprint == request.policy_fingerprint
        assert scored.read_completed_at == NOW and scored.context.principal.actor_id == "signed-manager"
        assert scored.effect == "read_or_suggestion_only_no_booking_contact_or_external_execution"
        assert base.invoke(db, user, institute, optimize) == scored
        refused = deepcopy(match); refused["arguments"]["policy"]["permission_requirement"] = "recorded_grant_required"
        assert base.invoke(db, user, institute, refused).result.unavailable_reason == "permission_requirement_unmet"
        for candidate in (match, optimize):
            stale = deepcopy(candidate); stale["arguments"]["expected_event_fingerprint"] = "0"*64
            with pytest.raises(HTTPException): base.invoke(db, user, institute, stale)
        with pytest.raises(HTTPException): base.invoke(db, user, "foreign", optimize)
        assert tuple(db.scalar(select(func.count()).select_from(m)) for m in models) == counts


def test_sqlite_registered_services_preserve_official_results_and_refusals(client, monkeypatch):
    institute, employee, service, *_ = setup(client)
    exercise(main_module.engine, institute, employee, service, monkeypatch)


def test_actual_postgres_registered_services_preserve_official_results_and_refusals(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)
