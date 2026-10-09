import pytest
from fastapi import HTTPException
from app.modules.copilot import voice
from app.modules.base.read_capabilities import Principal
from app.ai.contracts import Transcript

principal = Principal(actor_id="manager", institute_id="institute", role="responsable_institut")
audio = dict(audio=b"fixture audio", media_type="audio/wav", language="fr")

class Provider:
    def __init__(self, text): self.text = text
    def transcribe(self, request):
        assert request.audio == audio["audio"]
        return Transcript(text=self.text)

def test_official_base_voice_preview_preserves_exact_transcript_without_action():
    result = voice.preview(principal, audio, Provider("Consulter les stocks enregistres"))
    assert result.status == "review_required"
    assert result.route.status == "routed"
    assert result.route.framework_version == "1.5.1"
    assert result.transcript == "Consulter les stocks enregistres"
    assert result.effect == "transcript_intent_only_no_domain_action"

@pytest.mark.parametrize("text", ["", "   "])
def test_silent_audio_does_not_route(text):
    class Never:
        def resolve(self, text): raise AssertionError("Silent audio routed")
    assert voice.preview(principal, audio, Provider(text), Never()).status == "silent"

def test_disabled_and_failed_provider_are_controlled():
    with pytest.raises(HTTPException) as error: voice.preview(principal, audio, None)
    assert error.value.status_code == 503
    class Broken:
        def transcribe(self, request): raise RuntimeError("private provider details")
    with pytest.raises(HTTPException) as error: voice.preview(principal, audio, Broken())
    assert "private" not in error.value.detail

def test_oversized_transcript_does_not_route():
    with pytest.raises(HTTPException) as error: voice.preview(principal, audio, Provider("a"*2001))
    assert error.value.status_code == 422
