import hashlib
import json
import logging
import pytest
import app.main as main
from app.ai.contracts import Transcript
from app.core.logging_config import JsonLogFormatter
from app.modules.base import audit, upstream
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


@pytest.fixture
def voice_records():
    records = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(json.loads(JsonLogFormatter().format(record)))
    audit.logger.addHandler(handler)
    try:
        yield records
    finally:
        audit.logger.removeHandler(handler)


def test_voice_audit_correlates_signed_http_and_official_base_without_content(client, monkeypatch, voice_records):
    institute, _, _ = _bootstrap_reference_data(client)
    audio = b"PRIVATE_AUDIO_21O"
    transcript = "Consulter les stocks enregistres"
    class Provider:
        def transcribe(self, request):
            assert request.audio == audio
            return Transcript(text=transcript)
    monkeypatch.setattr(main.app.state.ai_providers, "stt", Provider())
    actual = upstream.OfficialRouter.resolve
    actors = []
    def observe(self, text):
        actors.append(json.loads(audit.upstream_actor.get()))
        return actual(self, text)
    monkeypatch.setattr(upstream.OfficialRouter, "resolve", observe)
    response = client.post("/api/v1/copilot/voice/preview?language=fr", content=audio,
        headers={**_auth_headers("responsable_institut", institute),
                 "Content-Type": "audio/wav", "X-Request-ID": "voice-correlation-21o"})
    assert response.status_code == 200, response.text
    records = [r for r in voice_records if r.get("audit_action") == "copilot_voice_preview"]
    assert [r["audit_event"] for r in records] == ["attempt", "outcome"]
    assert all(r["request_id"] == "voice-correlation-21o" for r in records)
    assert records[0]["audit_operation_id"] == records[1]["audit_operation_id"]
    assert actors == [{"operation_id": records[0]["audit_operation_id"], "actor_id": "test-user", "institute_id": institute}]
    assert records[1]["audit_audio_bytes"] == len(audio)
    assert records[1]["audit_status"] == "review_required"
    assert records[1]["audit_route_status"] == response.json()["route"]["status"]
    assert records[1].get("audit_process_id") == response.json()["route"]["process_id"]
    serialized = json.dumps(records)
    for private in (audio.decode(), transcript, hashlib.sha256(audio).hexdigest(), hashlib.sha256(transcript.encode()).hexdigest()):
        assert private not in serialized
    assert audit.upstream_actor.get() is None


@pytest.mark.parametrize("media,audio,status", [
    ("private/unsupported-21o", b"private-audio", 415),
    ("audio/wav", b"", 422),
    ("audio/wav", b"x" * 10_000_001, 413),
    ("audio/wav", b"private-audio", 503),
], ids=["unsupported", "empty", "oversized", "disabled"])
def test_voice_refusals_have_correlated_safe_outcomes(client, voice_records, media, audio, status):
    institute, _, _ = _bootstrap_reference_data(client)
    response = client.post("/api/v1/copilot/voice/preview", content=audio,
        headers={**_auth_headers("responsable_institut", institute), "Content-Type": media})
    assert response.status_code == status
    records = [r for r in voice_records if r.get("audit_action") == "copilot_voice_preview"]
    assert [r["audit_event"] for r in records] == ["attempt", "outcome"]
    assert records[0]["audit_operation_id"] == records[1]["audit_operation_id"]
    assert records[1]["audit_status"] == status
    assert "private" not in json.dumps(records)
    assert audit.upstream_actor.get() is None


def test_unauthorized_voice_has_no_upstream_audit_or_provider_use(client, voice_records):
    response = client.post("/api/v1/copilot/voice/preview", content=b"private-audio",
        headers={**_auth_headers("collaboratrice", "foreign"), "Content-Type": "audio/wav"})
    assert response.status_code == 403
    assert not any(r.get("audit_action") == "copilot_voice_preview" for r in voice_records)
    assert audit.upstream_actor.get() is None
