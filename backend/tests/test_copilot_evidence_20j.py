from datetime import datetime, timezone
import pytest
from app.modules.copilot import query


def evidence(**changes):
    now = datetime(2026, 10, 9, tzinfo=timezone.utc)
    return {"capability": "CLIENT_READ", "institute_id": "a", "captured_at": now,
        "read_completed_at": now, "fingerprint": "0" * 64,
        "result": query.CustomerFacts(customer_id="selected", institute_id="a", display_name="Registered", created_at=now), **changes}


def test_registered_result_cannot_be_relabelled_as_other_capability():
    assert query.Evidence(**evidence()).capability == "CLIENT_READ"
    for name in query.REGISTRY:
        if name != "CLIENT_READ":
            with pytest.raises(ValueError, match="registered capability"):
                query.Evidence(**evidence(capability=name))


def test_customer_scope_and_planning_capture_are_bound():
    with pytest.raises(ValueError, match="Customer source scope"):
        query.Evidence(**evidence(institute_id="foreign"))
    now = datetime(2026, 10, 9, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="Planning source capture"):
        query.Evidence(**evidence(capability="PLANNING_READ", result=query.query.PlanningFacts(
            generated_at=datetime(2026, 10, 8, tzinfo=timezone.utc), rows=())))
