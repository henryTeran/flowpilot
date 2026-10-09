"""Captured service evidence, explicit unknowns and hostile nested originals."""
from copy import deepcopy
import pytest
from app.modules.base import query
from app.modules.jv.operational import OperationalAnalyzer
from app.modules.waitlist.originals import fingerprint
from test_base_query_17q import prepared, body, post, MESSAGES


def seal(value):
    normalized = query.Evidence.model_validate({**value, "fingerprint": "0" * 64})
    return normalized.model_copy(update={"fingerprint": fingerprint(normalized.model_dump(mode="json", exclude={"fingerprint"}))})


def resolve(document, pointer):
    for part in pointer.lstrip("/").split("/"):
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document


def test_real_official_base_service_facts_have_replayable_source_bound_jv_analysis(client):
    institute, employee, ticket = prepared(client)
    analyzer = OperationalAnalyzer()
    for capability in MESSAGES:
        response = post(client, institute, body(capability, employee, ticket))
        assert response.status_code == 200, response.text
        source = response.json()["evidence"]
        evidence = query.Evidence.model_validate(source)
        result = analyzer.analyze(evidence)
        assert result == analyzer.analyze(evidence)
        assert result.evidence_fingerprint == source["fingerprint"]
        assert result.institute_id == institute and result.actions == ()
        assert result.fingerprint == fingerprint(result.model_dump(mode="json", exclude={"fingerprint"}))
        for metric in result.metrics:
            assert metric.sources and metric.unit == "count"
            for citation in metric.sources:
                assert citation.evidence_fingerprint == source["fingerprint"]
                resolve(source, citation.pointer)
        assert "revenue" in result.missing_facts and "causal_contributions" in result.missing_facts
        if capability == "QUEUE_READ":
            assert result.metrics[0].value == 1
        elif capability == "QUEUE_ASSIGNMENT_OPTIONS":
            assert [(d.employee_id, d.assignable, d.reason) for d in result.assignments] == [
                (o["employee_id"], o["assignable"], o["reason"]) for o in source["result"]["options"]]


def queue():
    return seal(dict(institute_id="scope", capability=query.REGISTRY["QUEUE_READ"].model_dump(mode="json"),
        captured_at="2026-10-09T10:00:00Z", read_completed_at="2026-10-09T10:00:01Z", result={"items": []}))


def test_known_empty_queue_is_zero_and_not_missing_revenue_or_demand():
    result = OperationalAnalyzer().analyze(queue())
    assert [m.value for m in result.metrics] == [0, 0]
    assert "queue_tickets" in result.observed_facts
    assert "unobserved_demand" in result.missing_facts
    assert "revenue" not in result.observed_facts


def test_tamper_wrong_capability_metadata_and_reversed_chronology_are_rejected():
    source = queue().model_dump(mode="json")
    changed = deepcopy(source); changed["institute_id"] = "changed"
    with pytest.raises(ValueError, match="digest mismatch"):
        OperationalAnalyzer().analyze(query.Evidence.model_validate(changed))
    changed = deepcopy(source); changed["capability"]["application_service"] = "invented.service"
    with pytest.raises(ValueError, match="metadata mismatch"):
        OperationalAnalyzer().analyze(seal(changed))
    changed = deepcopy(source); changed["capability"] = query.REGISTRY["PLANNING_READ"].model_dump(mode="json")
    with pytest.raises(ValueError, match="capability/result mismatch"):
        OperationalAnalyzer().analyze(seal(changed))
    changed = deepcopy(source); changed["captured_at"] = "2026-10-10T10:00:00Z"
    with pytest.raises(ValueError, match="chronology mismatch"):
        OperationalAnalyzer().analyze(seal(changed))


def test_source_assignability_is_not_recalculated_and_foreign_nested_scope_is_rejected():
    source = queue().model_dump(mode="json")
    source["capability"] = query.REGISTRY["QUEUE_ASSIGNMENT_OPTIONS"].model_dump(mode="json")
    source["result"] = {"ticket_id": "ticket", "options": [{"employee_id": "employee", "institute_id": "scope",
        "ticket_id": "ticket", "assignable": False, "available_from": "2026-10-09T10:00:00Z",
        "available_until": "2026-10-09T18:00:00Z", "service_duration_minutes": 30,
        "projected_end_time": "2026-10-09T10:30:00Z", "reason": "recorded_business_refusal",
        "blocking_appointment_id": None, "blocking_session_id": None}]}
    result = OperationalAnalyzer().analyze(seal(source))
    assert result.metrics[1].value == 0 and result.assignments[0].assignable is False
    assert result.assignments[0].reason == "recorded_business_refusal"
    source["result"]["options"][0]["institute_id"] = "foreign"
    with pytest.raises(ValueError, match="scope mismatch"):
        OperationalAnalyzer().analyze(seal(source))


def test_unchecked_nested_model_copy_cannot_bypass_boundary():
    source = queue()
    unsafe = source.model_copy(update={"result": source.result.model_copy(update={"items": [{"sql": "SELECT"}]})})
    with pytest.raises(ValueError):
        OperationalAnalyzer().analyze(unsafe)
