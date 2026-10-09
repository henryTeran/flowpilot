import logging
import pytest
from app.modules.base import audit
from app.modules.waitlist.originals import fingerprint
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


@pytest.fixture
def audit_records():
    records = []
    handler = logging.Handler()
    handler.emit = records.append
    audit.logger.addHandler(handler)
    try:
        yield records
    finally:
        audit.logger.removeHandler(handler)


def test_discovery_signed_correlation_and_scope_filter(client, audit_records):
    institute, _, _ = _bootstrap_reference_data(client)
    response = client.get("/api/v1/copilot/capabilities", headers=_auth_headers("accueil", institute))
    assert response.status_code == 200
    values = response.json()
    assert len(values) == 5
    assert all(value["audit"] == "signed_scope_interaction_id_and_source_digest_no_raw_message" for value in values)
    records = [record for record in audit_records if getattr(record, "audit_action", None) == "copilot_capabilities"]
    assert [record.audit_event for record in records] == ["attempt", "outcome"]
    assert records[0].audit_operation_id == records[1].audit_operation_id
    assert records[1].audit_response_digest == fingerprint(values)
    assert records[1].audit_actor_id == "test-user" and records[1].audit_institute_id == institute
    assert audit.upstream_actor.get() is None


def test_unauthorized_discovery_does_not_open_domain_audit(client, audit_records):
    response = client.get("/api/v1/copilot/capabilities", headers=_auth_headers("collaboratrice", "foreign"))
    assert response.status_code == 403
    assert not any(getattr(record, "audit_action", None) == "copilot_capabilities" for record in audit_records)
