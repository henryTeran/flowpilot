import app.main as main
from app.ai.contracts import Transcript
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def test_voice_signed_http_boundary_and_official_base(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    headers = {**_auth_headers("responsable_institut", institute), "Content-Type": "audio/wav"}
    path = "/api/v1/copilot/voice/preview?language=fr"
    assert client.post(path, content=b"audio").status_code == 403
    assert client.post(path, headers={**headers, "Content-Type":"application/json"}, content=b"audio").status_code == 415
    assert client.post(path, headers=headers, content=b"").status_code == 422
    assert client.post(path, headers=headers, content=b"x"*10_000_001).status_code == 413
    assert client.post(path, headers=headers, content=b"audio").status_code == 503
    class Provider:
        def transcribe(self, request):
            assert request.audio == b"audio" and request.language == "fr"
            return Transcript(text="Consulter les stocks enregistres")
    monkeypatch.setattr(main.app.state.ai_providers, "stt", Provider())
    response = client.post(path, headers=headers, content=b"audio")
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["transcript"] == "Consulter les stocks enregistres"
    assert value["route"]["framework_version"] == "1.5.1"
    assert value["status"] == "review_required"
    assert value["effect"] == "transcript_intent_only_no_domain_action"
    assert client.post(path+"x", headers=headers, content=b"audio").status_code == 422
