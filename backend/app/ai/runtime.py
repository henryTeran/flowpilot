"""Trusted server selection. No SDK import or client creation when disabled."""
from dataclasses import dataclass, field
from typing import Literal
from pydantic import SecretStr, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.ai.contracts import LLMProvider, SpeechToTextProvider, EmbeddingProvider


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLOWPILOT_AI_", frozen=True, extra="forbid", hide_input_in_errors=True)
    llm_provider: Literal["disabled", "fake", "openai"] = "disabled"
    stt_provider: Literal["disabled", "fake", "voxtral"] = "disabled"
    embedding_provider: Literal["disabled", "fake", "openai"] = "disabled"
    openai_api_key: SecretStr | None = None
    mistral_api_key: SecretStr | None = None
    llm_model: str | None = None
    embedding_model: str | None = None
    stt_model: str | None = None
    timeout_ms: int = Field(default=15000, ge=1, le=60000)

    @model_validator(mode="after")
    def configured(self):
        for selected, model, key in ((self.llm_provider == "openai", self.llm_model, self.openai_api_key),
            (self.embedding_provider == "openai", self.embedding_model, self.openai_api_key),
            (self.stt_provider == "voxtral", self.stt_model, self.mistral_api_key)):
            if selected and (model is None or not model.strip() or model != model.strip() or key is None or not key.get_secret_value().strip()):
                raise ValueError("Selected AI provider requires explicit model and credentials")
        return self


@dataclass
class Providers:
    llm: LLMProvider | None = None
    stt: SpeechToTextProvider | None = None
    embedding: EmbeddingProvider | None = None
    owned: list = field(default_factory=list, repr=False)
    _closed: bool = field(default=False, repr=False)

    def close(self):
        if self._closed:
            return
        self._closed = True
        failed = False
        for resource in reversed(self.owned):
            try:
                resource.close()
            except Exception:
                failed = True
        if failed:
            raise RuntimeError("AI provider cleanup failed")


def _openai(config):
    import httpx
    from openai import OpenAI
    from app.ai.openai_adapter import OpenAIProvider
    transport = httpx.Client(timeout=config.timeout_ms/1000, trust_env=False)
    try:
        client = OpenAI(api_key=config.openai_api_key.get_secret_value(), base_url="https://api.openai.com/v1",
            timeout=config.timeout_ms/1000, max_retries=0, http_client=transport)
        return OpenAIProvider(client, model=config.llm_model if config.llm_provider == "openai" else None,
            embedding_model=config.embedding_model if config.embedding_provider == "openai" else None)
    except Exception:
        transport.close()
        raise


def _voxtral(config):
    import httpx2
    from mistralai.client import Mistral
    from app.ai.voxtral_adapter import VoxtralProvider
    transport = httpx2.Client(timeout=config.timeout_ms/1000, trust_env=False)
    try:
        client = Mistral(api_key=config.mistral_api_key.get_secret_value(), server_url="https://api.mistral.ai",
            client=transport, retry_config=None, timeout_ms=config.timeout_ms)
        return VoxtralProvider(client, model=config.stt_model, timeout_ms=config.timeout_ms)
    except Exception:
        transport.close()
        raise


def build(config: AISettings, fake_bindings: Providers | None = None) -> Providers:
    config = AISettings.model_validate(config.model_dump())
    result = Providers()
    try:
        for name, selector in (("llm", config.llm_provider), ("stt", config.stt_provider), ("embedding", config.embedding_provider)):
            if selector == "fake":
                binding = getattr(fake_bindings, name, None)
                if binding is None:
                    raise ValueError("Fake AI provider requires an explicit server binding")
                setattr(result, name, binding)
        if config.llm_provider == "openai" or config.embedding_provider == "openai":
            adapter = _openai(config)
            result.owned.append(adapter)
            if config.llm_provider == "openai": result.llm = adapter
            if config.embedding_provider == "openai": result.embedding = adapter
        if config.stt_provider == "voxtral":
            adapter = _voxtral(config)
            result.owned.append(adapter)
            result.stt = adapter
        return result
    except Exception:
        result.close()
        raise
