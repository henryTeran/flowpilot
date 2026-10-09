"""Only this infrastructure adapter imports the OpenAI SDK."""
import json
from openai import OpenAI, APITimeoutError
from app.ai import contracts as c
from app.ai.boundary import validated, InvalidProviderResponse, ProviderTimeout, ProviderUnavailable


class OpenAIProvider:
    def __init__(self, client: OpenAI, *, model: str, embedding_model: str):
        if not model.strip() or not embedding_model.strip():
            raise ValueError("Explicit server models required")
        self.client, self.model, self.embedding_model = client, model, embedding_model

    def _call(self, method, **kwargs):
        try:
            return method(**kwargs)
        except APITimeoutError as error:
            raise ProviderTimeout() from error
        except Exception as error:
            raise ProviderUnavailable() from error

    def complete(self, candidate: c.CompletionRequest) -> c.Completion:
        request = validated(c.CompletionRequest, candidate)
        arguments = dict(model=self.model, input=[m.model_dump() for m in request.messages],
            max_output_tokens=request.max_output_tokens, store=False, tools=[])
        if request.output_schema is not None:
            arguments["text"] = {"format": {"type": "json_schema", "name": "flowpilot_response",
                "strict": True, "schema": request.output_schema}}
        result = self._call(self.client.responses.create, **arguments)
        try:
            if result.status != "completed" or not result.output:
                raise ValueError("Incomplete response")
            for item in result.output:
                if item.type == "reasoning":
                    continue
                if item.type != "message" or item.role != "assistant" or item.status != "completed" or any(part.type != "output_text" for part in item.content):
                    raise ValueError("Refused or unexpected output")
            text = result.output_text
            if not text:
                raise ValueError("Missing text")
            structured = json.loads(text) if request.output_schema is not None else None
            return c.Completion(text=text, structured=structured)
        except (ValueError, TypeError, AttributeError) as error:
            raise InvalidProviderResponse() from error

    def embed(self, candidate: c.EmbeddingRequest) -> c.Embeddings:
        request = validated(c.EmbeddingRequest, candidate)
        result = self._call(self.client.embeddings.create, model=self.embedding_model,
            input=list(request.texts), encoding_format="float")
        try:
            ordered = sorted(result.data, key=lambda row: row.index)
            if any(type(row.index) is not int for row in ordered) or [row.index for row in ordered] != list(range(len(request.texts))):
                raise ValueError("Embedding indexes missing or duplicated")
            return c.Embeddings(vectors=tuple(tuple(row.embedding) for row in ordered))
        except (ValueError, TypeError, AttributeError) as error:
            raise InvalidProviderResponse() from error

    def close(self):
        self.client.close()
