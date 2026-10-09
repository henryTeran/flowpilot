"""Explicit selection, SDK construction without requests and failure cleanup."""
import pytest
from fastapi.testclient import TestClient
from app.ai import runtime, fake, contracts as c, boundary as b
from app.main import create_app


def test_disabled_defaults_build_no_sdk_clients(monkeypatch):
    def forbidden(config): raise AssertionError("No remote selection")
    monkeypatch.setattr(runtime, "_openai", forbidden)
    monkeypatch.setattr(runtime, "_voxtral", forbidden)
    providers = runtime.build(runtime.AISettings())
    assert providers.llm is providers.stt is providers.embedding is None
    providers.close(); providers.close()


def test_selected_credentials_models_unknown_names_and_fake_bindings_fail_closed():
    for terms in ({"llm_provider": "unknown"}, {"llm_provider": "openai"},
        {"stt_provider": "voxtral", "mistral_api_key": "private-key"}, {"timeout_ms": 60001}):
        with pytest.raises(ValueError) as caught: runtime.AISettings(**terms)
        assert "private-key" not in str(caught.value)
    with pytest.raises(ValueError, match="explicit server binding"):
        runtime.build(runtime.AISettings(llm_provider="fake"))


def test_actual_sdk_construction_shared_openai_close_and_single_port_models(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://unselected.invalid")
    config = runtime.AISettings(llm_provider="openai", embedding_provider="openai", stt_provider="voxtral",
        openai_api_key="private-key", mistral_api_key="private-key", llm_model="configured-llm",
        embedding_model="configured-embedding", stt_model="configured-stt", timeout_ms=5000)
    assert "private-key" not in repr(config) and "private-key" not in config.model_dump_json()
    providers = runtime.build(config)
    assert providers.llm is providers.embedding
    assert str(providers.llm.client.base_url) == "https://api.openai.com/v1/"
    assert providers.llm.client.max_retries == 0
    openai_client = providers.llm.client
    mistral_http = providers.stt.client.sdk_configuration.client
    providers.close(); providers.close()
    assert openai_client.is_closed() and mistral_http.is_closed
    providers = runtime.build(runtime.AISettings(embedding_provider="openai", openai_api_key="test-only", embedding_model="embedding-only"))
    try:
        assert providers.llm is None and providers.embedding.model is None
        with pytest.raises(b.ProviderUnavailable):
            providers.embedding.complete(c.CompletionRequest(messages=(c.Message(role="user", content="x"),)))
    finally: providers.close()


def test_partial_construction_failure_closes_created_adapter(monkeypatch):
    closed = []
    class Resource:
        def close(self): closed.append("openai")
    monkeypatch.setattr(runtime, "_openai", lambda config: Resource())
    def fail(config): raise RuntimeError("second constructor failed")
    monkeypatch.setattr(runtime, "_voxtral", fail)
    config = runtime.AISettings(llm_provider="openai", stt_provider="voxtral", openai_api_key="test", mistral_api_key="test", llm_model="llm", stt_model="stt")
    with pytest.raises(RuntimeError): runtime.build(config)
    assert closed == ["openai"]


def test_cleanup_attempts_all_resources_even_if_one_fails():
    closed = []
    class Resource:
        def __init__(self, label, fails=False): self.label, self.fails = label, fails
        def close(self):
            closed.append(self.label)
            if self.fails: raise RuntimeError("private failure")
    providers = runtime.Providers(owned=[Resource("first"), Resource("last", True)])
    with pytest.raises(RuntimeError, match="AI provider cleanup failed"): providers.close()
    providers.close()
    assert closed == ["last", "first"]


def test_real_application_lifespan_initializes_and_closes_owned_provider(monkeypatch):
    class OwnedFake(fake.FakeLLMProvider):
        closed = False
        def close(self): self.closed = True
    llm = OwnedFake(c.Completion(text="offline"))
    monkeypatch.setattr(runtime, "_openai", lambda config: llm)
    application = create_app(ai_config=runtime.AISettings(llm_provider="openai", openai_api_key="test-only", llm_model="configured-model"))
    with TestClient(application):
        assert application.state.ai_providers.llm is llm
        assert not application.state.ai_providers._closed
    assert application.state.ai_providers._closed
    assert llm.closed


def test_explicit_fake_binding_is_borrowed_and_works_without_remote_clients():
    llm = fake.FakeLLMProvider(c.Completion(text="offline"))
    providers = runtime.build(runtime.AISettings(llm_provider="fake"), runtime.Providers(llm=llm))
    assert b.complete(providers.llm, c.CompletionRequest(messages=(c.Message(role="user", content="x"),))).text == "offline"
    assert providers.owned == []
    providers.close()
