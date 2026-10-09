"""Validate both sides of infrastructure ports, without SDK error leakage."""
from app.ai import contracts as c


class ProviderUnavailable(Exception):
    def __init__(self): super().__init__("AI provider unavailable")


class ProviderTimeout(ProviderUnavailable):
    def __init__(self): Exception.__init__(self, "AI provider timeout")


class InvalidProviderResponse(Exception):
    def __init__(self): super().__init__("AI provider response invalid")


def validated(model, value):
    if isinstance(value, model):
        # JSON reconstructs nested unchecked copies while preserving typed tuples.
        # Audio bytes stay bytes, not a lossy JSON encoding of arbitrary audio.
        if model is c.AudioRequest:
            return model.model_validate(value.model_dump())
        return model.model_validate_json(value.model_dump_json())
    return model.model_validate(value)


def invoke(method, request, result_model):
    try:
        raw = method(request)
    except (TimeoutError, ProviderTimeout) as error:
        raise ProviderTimeout() from error
    except InvalidProviderResponse as error:
        raise InvalidProviderResponse() from error
    except Exception as error:
        raise ProviderUnavailable() from error
    try:
        return validated(result_model, raw)
    except (ValueError, TypeError, AttributeError) as error:
        raise InvalidProviderResponse() from error


def complete(provider: c.LLMProvider, candidate) -> c.Completion:
    request = validated(c.CompletionRequest, candidate)
    return invoke(provider.complete, request, c.Completion)


def transcribe(provider: c.SpeechToTextProvider, candidate) -> c.Transcript:
    request = validated(c.AudioRequest, candidate)
    return invoke(provider.transcribe, request, c.Transcript)


def embed(provider: c.EmbeddingProvider, candidate) -> c.Embeddings:
    request = validated(c.EmbeddingRequest, candidate)
    result = invoke(provider.embed, request, c.Embeddings)
    if len(result.vectors) != len(request.texts):
        raise InvalidProviderResponse()
    return result
