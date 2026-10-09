"""Bounded provider-independent values. Model output never authorizes effects."""
from typing import Annotated, Literal, Protocol
import json
import math
from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strict=True, max_length=64000)]


class Value(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Message(Value):
    role: Literal["system", "user", "assistant"]
    content: Text


class CompletionRequest(Value):
    messages: Annotated[tuple[Message, ...], Field(min_length=1, max_length=50)]
    max_output_tokens: Annotated[int, Field(strict=True, ge=1, le=8192)] = 1024
    output_schema: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def bounded(self):
        if sum(len(m.content) for m in self.messages) > 64000:
            raise ValueError("Provider prompt too large")
        if self.output_schema is not None and len(json.dumps(self.output_schema, allow_nan=False).encode("utf-8")) > 64000:
            raise ValueError("Provider schema too large")
        return self


class Completion(Value):
    text: Text
    structured: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def bounded(self):
        if self.structured is not None and len(json.dumps(self.structured, allow_nan=False).encode("utf-8")) > 64000:
            raise ValueError("Provider result too large")
        return self


class AudioRequest(Value):
    audio: Annotated[bytes, Field(min_length=1, max_length=10_000_000)]
    media_type: Literal["audio/wav", "audio/mpeg", "audio/webm", "audio/mp4", "audio/ogg"]
    language: Literal["fr", "en", "de", "it"] | None = None


class Transcript(Value):
    text: Text  # Empty/silent audio is not an invented utterance.


class EmbeddingRequest(Value):
    texts: Annotated[tuple[Text, ...], Field(min_length=1, max_length=128)]

    @model_validator(mode="after")
    def bounded(self):
        if any(not text.strip() for text in self.texts) or sum(len(text) for text in self.texts) > 64000:
            raise ValueError("Provider embedding input invalid")
        return self


class Embeddings(Value):
    vectors: Annotated[tuple[tuple[float, ...], ...], Field(min_length=1, max_length=128)]

    @model_validator(mode="after")
    def coherent(self):
        size = len(self.vectors[0])
        if not 1 <= size <= 8192 or any(len(v) != size or any(not math.isfinite(x) for x in v) for v in self.vectors):
            raise ValueError("Provider embeddings require finite equal dimensions")
        return self


class LLMProvider(Protocol):
    def complete(self, request: CompletionRequest) -> Completion: ...


class SpeechToTextProvider(Protocol):
    def transcribe(self, request: AudioRequest) -> Transcript: ...


class EmbeddingProvider(Protocol):
    def embed(self, request: EmbeddingRequest) -> Embeddings: ...
