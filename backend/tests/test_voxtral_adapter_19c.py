"""Real Mistral SDK requests/response parsing, mocked HTTP only."""
import httpx2 as httpx
import pytest
from mistralai.client import Mistral
from app.ai import contracts as c, boundary as b
from app.ai.voxtral_adapter import VoxtralProvider


def provider(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return VoxtralProvider(Mistral(api_key="test-only-key", client=client, retry_config=None, timeout_ms=5000), model="configured-voxtral", timeout_ms=5000)


def payload(text="Bonjour"):
    return {"model": "configured-voxtral", "text": text, "language": "fr", "segments": [],
        "usage": {"prompt_audio_seconds": 1, "prompt_tokens": 0, "total_tokens": 2, "completion_tokens": 2}}


def audio(): return c.AudioRequest(audio=b"RIFF\xff\x00\xfeWAVE", media_type="audio/wav", language="fr")


@pytest.mark.parametrize("text", ["Bonjour", ""])
def test_binary_upload_model_language_and_silent_response(text):
    seen = []
    def handler(request):
        content = request.read(); seen.append(content)
        assert request.url.path == "/v1/audio/transcriptions"
        assert request.headers["content-type"].startswith("multipart/form-data")
        assert audio().audio in content and b"audio.wav" in content
        assert b"configured-voxtral" in content and b"name=\"language\"" in content and b"fr" in content
        assert b"file_url" not in content and b"file_id" not in content
        return httpx.Response(200, json=payload(text))
    adapter = provider(handler)
    try:
        assert b.transcribe(adapter, audio()).text == text
        assert len(seen) == 1
    finally: adapter.close()


def test_timeout_and_auth_failure_are_sanitized_without_retries():
    for kind, expected in [("timeout", b.ProviderTimeout), ("auth", b.ProviderUnavailable)]:
        seen = []
        def handler(request):
            seen.append(request)
            if kind == "timeout": raise httpx.ReadTimeout("private endpoint", request=request)
            return httpx.Response(401, json={"message": "private API key details"})
        adapter = provider(handler)
        try:
            with pytest.raises(expected) as caught: b.transcribe(adapter, audio())
            assert len(seen) == 1 and "private" not in str(caught.value)
        finally: adapter.close()


def test_invalid_input_never_uploads_and_close_releases_http_client():
    def forbidden(request): raise AssertionError("Must not upload")
    adapter = provider(forbidden)
    transport = adapter.client.sdk_configuration.client
    try:
        with pytest.raises(ValueError):
            b.transcribe(adapter, audio().model_copy(update={"media_type": "text/plain"}))
    finally: adapter.close()
    assert transport.is_closed


@pytest.mark.parametrize("value", [{"model": "configured-voxtral"}, {**payload(), "text": None}])
def test_malformed_sdk_response_is_not_a_transcript_or_silence(value):
    adapter = provider(lambda request: httpx.Response(200, json=value))
    try:
        with pytest.raises(b.InvalidProviderResponse): b.transcribe(adapter, audio())
    finally: adapter.close()
