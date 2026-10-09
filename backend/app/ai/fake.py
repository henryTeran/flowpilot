"""Scripted offline providers: no remote request, business access or credentials."""
from app.ai import contracts as c


class FakeLLMProvider:
    def __init__(self, response: c.Completion): self.response = response
    def complete(self, request: c.CompletionRequest) -> c.Completion: return self.response


class FakeSpeechToTextProvider:
    def __init__(self, response: c.Transcript): self.response = response
    def transcribe(self, request: c.AudioRequest) -> c.Transcript: return self.response


class FakeEmbeddingProvider:
    def __init__(self, response: c.Embeddings): self.response = response
    def embed(self, request: c.EmbeddingRequest) -> c.Embeddings: return self.response
