import json
import hashlib
from pathlib import Path
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from fastapi import HTTPException
import pytest
from app.core.logging_config import JsonLogFormatter
from app.core.config import settings
from app.modules.base import audit, upstream
from app.modules.base import routes
from test_base_query_17q import prepared, post, body
from test_ticket_workflow import _auth_headers


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []
    def emit(self, record):
        self.records.append(json.loads(JsonLogFormatter().format(record)))


def test_actual_api_audit_http_correlation_upstream_actor_and_no_raw_payload(client, monkeypatch):
    institute, employee, ticket = prepared(client)
    capture = Capture()
    audit.logger.addHandler(capture)
    actual = upstream.OfficialRouter.resolve
    actors = []
    def observed(self, message):
        actors.append(json.loads(audit.upstream_actor.get()))
        return actual(self, message)
    monkeypatch.setattr(upstream.OfficialRouter, "resolve", observed)
    candidate = body("QUEUE_READ", employee, ticket)
    try:
        response = client.post("/api/v1/base/query", json=candidate,
            headers={**_auth_headers("accueil", institute), "X-Request-ID": "correlation-17u"})
    finally:
        audit.logger.removeHandler(capture)
    assert response.status_code == 200, response.text
    records = capture.records
    assert [r["audit_event"] for r in records] == ["attempt", "outcome"]
    assert all(r["request_id"] == "correlation-17u" for r in records)
    assert all(r["audit_operation_id"] == response.json()["request_id"] for r in records)
    assert actors == [{"operation_id": response.json()["request_id"], "actor_id": "test-user", "institute_id": institute}]
    assert records[-1]["audit_evidence_digest"] == response.json()["evidence"]["fingerprint"]
    assert records[-1]["audit_status"] == "answered"
    assert candidate["message"] not in json.dumps(records)
    assert audit.upstream_actor.get() is None
    root = Path(settings.BASE_RUNTIME_DIRECTORY) if settings.BASE_RUNTIME_DIRECTORY else Path(__file__).resolve().parents[2] / "integrations" / "base"
    matched = []
    for trace_file in (root / "workspace" / ".ai" / "trace").glob("*.jsonl"):
        for line in trace_file.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry.get("actor") == json.dumps(actors[0], separators=(",", ":")):
                matched.append(entry)
    expected_hash = "sha256:" + hashlib.sha256(json.dumps([candidate["message"]], ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert any(entry["op"] == "route" and entry["args_hash"] == expected_hash for entry in matched)
    assert all("request" not in entry and candidate["message"] not in json.dumps(entry) for entry in matched)


def test_refusal_and_failure_audit_do_not_record_private_exception_and_reset_context():
    principal = audit.Principal(actor_id="signed", institute_id="scope", role="responsable_institut")
    capture = Capture()
    audit.logger.addHandler(capture)
    try:
        for exception in (HTTPException(404, "private selected data"), RuntimeError("private provider secret")):
            with pytest.raises(type(exception)):
                with audit.trace(principal, "query", {"message": "private utterance"}):
                    raise exception
            assert audit.upstream_actor.get() is None
    finally:
        audit.logger.removeHandler(capture)
    assert [r.get("audit_status") for r in capture.records if r["audit_event"] == "outcome"] == [404, 500]
    assert "private" not in json.dumps(capture.records)


def test_concurrent_audit_contexts_do_not_share_actor_or_operation():
    barrier = Barrier(2)
    def work(index):
        principal = audit.Principal(actor_id=f"actor-{index}", institute_id=f"scope-{index}", role="accueil")
        with audit.trace(principal, "query", {"message": "bounded"}) as span:
            barrier.wait(timeout=5)
            actor = json.loads(audit.upstream_actor.get())
            assert actor == {"operation_id": span.id, "actor_id": principal.actor_id, "institute_id": principal.institute_id}
        assert audit.upstream_actor.get() is None
        return span.id
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(work, (1, 2)))
    assert len(set(ids)) == 2 and audit.upstream_actor.get() is None


def test_all_existing_signed_base_handlers_have_closed_audit_actions():
    assert {getattr(route.endpoint, "_base_audit_action", None) for route in routes.router.routes} == audit.ROUTE_ACTIONS
    with pytest.raises(ValueError): audit.traced("arbitrary_sql")
