"""Voxtral transcription SDK isolated from all business modules."""
import httpx2 as httpx
from mistralai.client import Mistral
from mistralai.client.errors import ResponseValidationError
from app.ai import contracts as c
from app.ai.boundary import validated, ProviderTimeout, ProviderUnavailable, InvalidProviderResponse

EXTENSIONS = {"audio/wav": "wav", "audio/mpeg": "mp3", "audio/webm": "webm", "audio/mp4": "mp4", "audio/ogg": "ogg"}


class VoxtralProvider:
    def __init__(self, client: Mistral, *, model: str, timeout_ms: int = 15000):
        if not model.strip() or type(timeout_ms) is not int or not 1 <= timeout_ms <= 60000:
            raise ValueError("Explicit server model and bounded timeout required")
        self.client, self.model, self.timeout_ms = client, model, timeout_ms

    def transcribe(self, candidate: c.AudioRequest) -> c.Transcript:
        request = validated(c.AudioRequest, candidate)
        arguments = dict(model=self.model,
            file={"file_name": f"audio.{EXTENSIONS[request.media_type]}", "content": request.audio},
            diarize=False, retries=None, timeout_ms=self.timeout_ms)
        if request.language is not None:
            arguments["language"] = request.language
        try:
            result = self.client.audio.transcriptions.complete(**arguments)
        except (httpx.TimeoutException, TimeoutError) as error:
            raise ProviderTimeout() from error
        except ResponseValidationError as error:
            raise InvalidProviderResponse() from error
        except Exception as error:
            raise ProviderUnavailable() from error
        try:
            return c.Transcript(text=result.text)
        except (ValueError, TypeError, AttributeError) as error:
            raise InvalidProviderResponse() from error

    def close(self):
        client = self.client.sdk_configuration.client
        if client is not None:
            client.close()
        self.client.__exit__(None, None, None)
