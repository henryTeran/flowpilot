"""Actual sovereign score reuse, unknowns, hostile scores and signed capture."""
from copy import deepcopy
import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.jv import scoring
from app.modules.optimizer import sources, originals, policy, domain
from app.modules.waitlist.originals import fingerprint
from test_optimizer_sources_16d import prepare
from test_optimizer_originals_16c import request as policy_request
from test_optimizer_policy_16b import rule
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def exercise(client, engine, institute, employee, service, monkeypatch):
    request = prepare(engine, institute, employee, service, monkeypatch)
    path = f"/api/v1/jv/institutes/{institute}/optimization"
    headers = _auth_headers("responsable_institut", institute)
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", collect)
    try:
        response = client.post(path, json=request.model_dump(mode="json"), headers=headers)
        assert response.status_code == 200, response.text
        value = response.json(); analysis = value["analysis"]; source = value["source"]
        assert analysis["ranking"] == "complete" and analysis["actions"] == []
        assert analysis["evidence_fingerprint"] == fingerprint(source)
        assert analysis["policy_fingerprint"] == request.policy_fingerprint
        for index, alternative in enumerate(analysis["alternatives"]):
            for field in ("option", "score", "rank", "state", "reasons", "contributions", "constraints"):
                assert alternative[field] == source["review"]["options"][index][field]
            assert alternative["sources"][0]["pointer"] == f"/review/options/{index}"
        assert analysis["fingerprint"] == fingerprint({k: v for k, v in analysis.items() if k != "fingerprint"})
        captured = sources.Read.model_validate(source)
        assert scoring.analyze(captured) == scoring.analyze(captured)
        changed = deepcopy(source)
        changed["review"]["options"][0]["score"]["numerator"] = "999999"
        with pytest.raises(ValueError, match="scoring proof"):
            scoring.analyze(sources.Read.model_validate(changed))
        changed = deepcopy(source); changed["policy_original"]["original"]["reason"] = "Changed explicit policy"
        with pytest.raises(ValueError, match="policy digest"):
            scoring.analyze(sources.Read.model_validate(changed))
    finally:
        event.remove(engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}
    for role, scope in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        assert client.post(path, json=request.model_dump(mode="json"), headers=_auth_headers(role, scope)).status_code == 403
    for field in ("score", "evidence", "weights", "actor_id", "institute_id", "provider"):
        assert client.post(path, json={**request.model_dump(mode="json"), field: "injected"}, headers=headers).status_code == 422


def test_sqlite_signed_exact_scoring_reuse_and_tamper_refusals(client, monkeypatch):
    institute, employee, service, *_ = setup(client)
    exercise(client, main_module.engine, institute, employee, service, monkeypatch)


def test_actual_postgres_signed_exact_scoring_reuse(client, postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, engine, institute, employee, service, monkeypatch)


def test_weighted_unknown_is_not_zero_and_prevents_complete_ranking(client, monkeypatch):
    institute, employee, service, *_ = setup(client)
    request = prepare(main_module.engine, institute, employee, service, monkeypatch)
    terms = policy.Terms(rules=[rule(f, enabled=f == "revenue_score") for f in domain.FACTORS])
    with Session(main_module.engine) as db:
        receipt = originals.create(db, institute, policy_request("jv-revenue-unknown").model_copy(update={"terms": terms}), "signed-manager")
        source = sources.read(db, institute, request.model_copy(update={"policy_id": receipt.original["id"], "policy_fingerprint": receipt.fingerprint}))
    analysis = scoring.analyze(source)
    assert analysis.ranking == "incomplete_evidence"
    assert analysis.alternatives and all(a.rank is None and a.score is None for a in analysis.alternatives)
    assert all(next(c for c in a.contributions if c.factor == "revenue_score").state == "unavailable" for a in analysis.alternatives)


def test_refused_source_remains_unavailable_without_ranking(client, monkeypatch):
    institute, employee, service, *_ = setup(client)
    request = prepare(main_module.engine, institute, employee, service, monkeypatch)
    changed = request.model_dump(mode="json")
    changed["matching_policy"]["permission_requirement"] = "recorded_grant_required"
    with Session(main_module.engine) as db:
        source = sources.read(db, institute, sources.Request.model_validate(changed))
    analysis = scoring.analyze(source)
    assert analysis.ranking == "source_unavailable" and analysis.alternatives == ()
    assert analysis.unavailable_reason == "permission_requirement_unmet"
    altered = source.model_dump(mode="json")
    altered["policy_original"]["original"]["institute_id"] = "foreign"
    altered["policy_original"]["fingerprint"] = fingerprint(altered["policy_original"]["original"])
    with pytest.raises(ValueError, match="scope/chronology"):
        scoring.analyze(sources.Read.model_validate(altered))
