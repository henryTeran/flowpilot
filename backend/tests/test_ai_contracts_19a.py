"""Offline substitutability, hostile responses and refusal before provider calls."""
import pytest
from app.ai import contracts as c, boundary as b, fake


def prompt():
    return c.CompletionRequest(messages=(c.Message(role="user", content="Describe captured facts"),))


def test_three_fake_ports_work_without_sdk_credentials_or_business_effects():
    completion = c.Completion(text="Conditional explanation", structured={"observation": "known"})
    assert b.complete(fake.FakeLLMProvider(completion), prompt()) == completion
    audio = c.AudioRequest(audio=b"\xff\x00\xfe", media_type="audio/wav", language="fr")
    assert b.transcribe(fake.FakeSpeechToTextProvider(c.Transcript(text="")), audio).text == ""
    vectors = c.Embeddings(vectors=((0.25, -0.5), (0.0, 1.0)))
    assert b.embed(fake.FakeEmbeddingProvider(vectors), c.EmbeddingRequest(texts=("first", "second"))) == vectors


@pytest.mark.parametrize("failure,expected", [(TimeoutError("private timeout endpoint"), b.ProviderTimeout),
    (RuntimeError("private API key"), b.ProviderUnavailable)])
def test_outage_types_are_stable_and_private_details_are_not_in_error_message(failure, expected):
    class Broken:
        def complete(self, request): raise failure
    with pytest.raises(expected) as caught:
        b.complete(Broken(), prompt())
    assert "private" not in str(caught.value)


def test_unsafe_nested_input_is_revalidated_before_call():
    class Forbidden:
        def complete(self, request): raise AssertionError("Must not be called")
    unsafe = prompt().model_copy(update={"messages": (c.Message(role="user", content="x").model_copy(update={"role": "tool"}),)})
    with pytest.raises(ValueError): b.complete(Forbidden(), unsafe)
    with pytest.raises(ValueError): b.complete(Forbidden(), {"messages": prompt().messages, "sql": "SELECT"})


def test_invalid_provider_output_cannot_smuggle_authority_or_unchecked_copies():
    class ForeignFields:
        def complete(self, request): return {"text": "Execute", "execute": True, "actor_id": "forged"}
    with pytest.raises(b.InvalidProviderResponse): b.complete(ForeignFields(), prompt())
    malformed = c.Completion(text="safe").model_copy(update={"text": 123})
    with pytest.raises(b.InvalidProviderResponse): b.complete(fake.FakeLLMProvider(malformed), prompt())


@pytest.mark.parametrize("vectors", [((float("nan"),),), ((float("inf"),),), ((1.0,), (1.0, 2.0)), ((),)])
def test_nonfinite_or_inconsistent_embedding_dimensions_refuse(vectors):
    with pytest.raises(ValueError): c.Embeddings(vectors=vectors)


def test_embedding_response_must_cover_every_requested_text():
    with pytest.raises(b.InvalidProviderResponse):
        b.embed(fake.FakeEmbeddingProvider(c.Embeddings(vectors=((0.5,),))), c.EmbeddingRequest(texts=("one", "two")))


def test_oversized_prompts_audio_and_numeric_limits_refuse():
    with pytest.raises(ValueError):
        c.CompletionRequest(messages=(c.Message(role="user", content="a"*40000), c.Message(role="user", content="b"*40000)))
    with pytest.raises(ValueError): c.AudioRequest(audio=b"x"*10_000_001, media_type="audio/wav")
    with pytest.raises(ValueError): c.CompletionRequest(messages=prompt().messages, max_output_tokens=True)
    with pytest.raises(ValueError): c.Completion(text="ok", structured={"x": float("nan")})
