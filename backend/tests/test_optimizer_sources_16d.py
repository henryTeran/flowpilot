from datetime import timedelta
from fractions import Fraction
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.optimizer import sources, originals, policy, domain
from app.modules.optimizer.models import PolicyOriginal
from app.modules.waitlist.models import DemandOriginal, LifecycleOriginal
from app.modules.appointments.models import Appointment
from app.modules.resources.models import Resource
from test_waitlist_sources_15d import prepare_sources
from test_optimizer_originals_16c import request as policy_request
from test_optimizer_policy_16b import rule
from test_waitlist_matching_15a import NOW
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def prepare(engine, institute, employee, service, monkeypatch):
    root, event = prepare_sources(engine, institute, employee, service, monkeypatch)
    for module in (sources, originals): monkeypatch.setattr(module, "utcnow", lambda: NOW)
    with Session(engine) as db:
        receipt = originals.create(db, institute, policy_request(), "signed-manager")
    return sources.Request(policy_id=receipt.original["id"], policy_fingerprint=receipt.fingerprint,
        root_id=root.original["id"], expected_event_id=event.original["id"], expected_event_fingerprint=event.fingerprint,
        horizon_end=NOW+timedelta(hours=3), matching_policy=dict(channel="email", history_requirement="review_only", permission_requirement="review_only"))


def exercise(engine, institute, employee, service, monkeypatch):
    request = prepare(engine, institute, employee, service, monkeypatch)
    with Session(engine) as db:
        counts = tuple(db.scalar(select(func.count()).select_from(model)) for model in (PolicyOriginal, DemandOriginal, LifecycleOriginal, Appointment))
        result = sources.read(db, institute, request)
        assert result.captured_at == result.source.captured_at == result.review.captured_at == NOW
        assert result.review.ranking == "complete" and result.review.options[0].rank == 1
        proof = result.proofs[0]
        factors = {f.rule.factor: f for f in proof.factors}
        duration = proof.option.end-proof.option.start
        window = proof.containing_employee_window.end-proof.containing_employee_window.start
        assert factors["utilization_score"].observation.value.fraction() == Fraction(duration//timedelta(microseconds=1), window//timedelta(microseconds=1))
        assert factors["idle_gap_penalty"].source.quantity == "3600000000"
        assert factors["resource_conflict_penalty"].observation.value.fraction() == 0
        for f in sources.UNKNOWN:
            assert factors[f].source.quantity is None and factors[f].observation.value is None
        assert result.catalog.currency == "not_recorded"
        assert result.policy_original.fingerprint == request.policy_fingerprint
        assert sources.read(db, institute, request) == result
        for field in ("policy_fingerprint", "expected_event_fingerprint"):
            with pytest.raises(HTTPException) as error:
                sources.read(db, institute, request.model_copy(update={field: "0"*64}))
            assert error.value.status_code == 400
        refused = sources.read(db, institute, request.model_copy(update={"matching_policy": request.matching_policy.model_copy(update={"permission_requirement": "recorded_grant_required"})}))
        assert refused.source.unavailable_reason == "permission_requirement_unmet"
        assert refused.review is None and refused.proofs == () and refused.catalog is None
        terms = policy.Terms(rules=[rule(f, enabled=f in {"utilization_score", "revenue_score"}) for f in domain.FACTORS])
        receipt = originals.create(db, institute, policy_request("unknown-revenue").model_copy(update={"terms": terms}), "signed-manager")
        unknown = sources.read(db, institute, request.model_copy(update={"policy_id": receipt.original["id"], "policy_fingerprint": receipt.fingerprint}))
        assert unknown.review.ranking == "incomplete_evidence"
        assert all(o.rank is None and o.score is None for o in unknown.review.options)
        db.add(Appointment(id="optimizer-block", institute_id=institute, employee_id=employee, service_id=service,
            customer_id="waitlist-customer", customer_name="Fixture", start_time=NOW+timedelta(hours=1), end_time=NOW+timedelta(hours=2), status="confirmed"))
        db.commit()
        blocked = sources.read(db, institute, request)
        assert blocked.review.ranking == "no_admissible_options" and not blocked.proofs
        assert tuple(db.scalar(select(func.count()).select_from(model)) for model in (PolicyOriginal, DemandOriginal, LifecycleOriginal, Appointment)) == (counts[0]+1, counts[1], counts[2], counts[3]+1)
    return request


def test_sqlite_current_score_and_source_refusals(client, monkeypatch):
    institute, employee, service, *_ = setup(client)
    exercise(main_module.engine, institute, employee, service, monkeypatch)


def test_actual_postgres_current_score_and_source_refusals(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)


def test_signed_current_review_rejects_client_truth_and_cross_scope(client, monkeypatch):
    institute, employee, service, *_ = setup(client)
    request = prepare(main_module.engine, institute, employee, service, monkeypatch)
    path = f"/api/v1/optimizer/institutes/{institute}/reviews/current"
    body = request.model_dump(mode="json")
    headers = _auth_headers("responsable_institut", institute)
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["review"]["ranking"] == "complete"
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        assert client.post(path, json=body, headers=_auth_headers(role, owner)).status_code == 403
    assert client.post(path, json=body).status_code == 403
    for field in ("score", "captured_at", "factors", "capacity", "actor_id", "institute_id"):
        assert client.post(path, json={**body, field: "injected"}, headers=headers).status_code == 422
    assert client.post(path, json={**body, "horizon_end": "2026-10-09"}, headers=headers).status_code == 422
    with Session(main_module.engine) as db:
        row = db.get(PolicyOriginal, request.policy_id)
        row.original = {**row.original, "reason": "Altered source"}; db.commit()
    assert client.post(path, json=body, headers=headers).status_code == 400


def test_every_unavailable_weighted_factor_prevents_ranking_and_elapsed_policy_retains_saturation(client, monkeypatch):
    institute, employee, service, *_ = setup(client)
    request = prepare(main_module.engine, institute, employee, service, monkeypatch)
    with Session(main_module.engine) as db:
        for factor in sources.UNKNOWN:
            terms = policy.Terms(rules=[rule(f, enabled=f == factor) for f in domain.FACTORS])
            receipt = originals.create(db, institute, policy_request(factor).model_copy(update={"terms": terms}), "signed-manager")
            read = sources.read(db, institute, request.model_copy(update={"policy_id": receipt.original["id"], "policy_fingerprint": receipt.fingerprint}))
            assert read.review.ranking == "incomplete_evidence"
            assert all(o.rank is None and o.score is None for o in read.review.options)
        terms = policy.Terms(rules=[rule(f, enabled=f == "idle_gap_penalty") for f in domain.FACTORS])
        receipt = originals.create(db, institute, policy_request("delay").model_copy(update={"terms": terms}), "signed-manager")
        read = sources.read(db, institute, request.model_copy(update={"policy_id": receipt.original["id"], "policy_fingerprint": receipt.fingerprint}))
        factor = next(f for f in read.proofs[0].factors if f.rule.factor == "idle_gap_penalty")
        assert factor.saturated == "yes" and factor.source.quantity == "3600000000" and factor.rule.ceiling == "60000000"
        assert read.review.options[0].score == domain.ExactScore(numerator="-1", denominator="1")


def test_current_corruption_expired_horizon_and_future_policy_refuse(client, monkeypatch):
    institute, employee, service, *_ = setup(client)
    request = prepare(main_module.engine, institute, employee, service, monkeypatch)
    with Session(main_module.engine) as db:
        with pytest.raises(HTTPException): sources.read(db, institute, request.model_copy(update={"horizon_end": NOW}))
        with pytest.raises(HTTPException) as missing: sources.read(db, institute, request.model_copy(update={"policy_id": "missing"}))
        assert missing.value.status_code == 404
        row = db.get(PolicyOriginal, request.policy_id)
        previous = row.original
        future = NOW+timedelta(microseconds=1)
        row.created_at = future
        row.original = {**previous, "created_at": future.isoformat().replace("+00:00", "Z")}
        row.fingerprint = originals.fingerprint(row.original); db.commit()
        with pytest.raises(HTTPException): sources.read(db, institute, request.model_copy(update={"policy_fingerprint": row.fingerprint}))
        row.created_at = NOW; row.original = previous; row.fingerprint = request.policy_fingerprint
        db.get(Resource, "waitlist-room").capabilities = [1]; db.commit()
        with pytest.raises(HTTPException): sources.read(db, institute, request)
