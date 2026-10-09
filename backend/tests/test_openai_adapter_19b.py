"""Actual SDK serialization/parsing via mocked HTTP transport, no remote calls."""
import json
import httpx
import pytest
from openai import OpenAI
from app.ai import contracts as c, boundary as b
from app.ai.openai_adapter import OpenAIProvider


def provider(handler):
    return OpenAIProvider(OpenAI(api_key="test-only-key", max_retries=0, timeout=5,
        http_client=httpx.Client(transport=httpx.MockTransport(handler))), model="configured-model", embedding_model="configured-embedding")


def response(text="hello", status="completed"):
    return {"id": "resp_test", "object": "response", "created_at": 1, "model": "configured-model", "status": status,
        "output": [{"id": "msg_test", "type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}]}]}


def prompt(schema=None):
    return c.CompletionRequest(messages=(c.Message(role="user", content="Captured facts"),), output_schema=schema)


def test_actual_sdk_responses_shape_and_structured_parse_without_tools_or_storage():
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        assert request.url.path == "/v1/responses"
        return httpx.Response(200, json=response('{"answer":"known"}'))
    adapter = provider(handler)
    try:
        result = b.complete(adapter, prompt({"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"], "additionalProperties": False}))
        assert result.structured == {"answer": "known"}
        assert seen[0]["store"] is False and seen[0]["tools"] == []
        assert seen[0]["text"]["format"]["strict"] is True
        assert seen[0]["model"] == "configured-model" and seen[0]["max_output_tokens"] == 1024
    finally: adapter.close()


@pytest.mark.parametrize("status,text", [("incomplete", "partial"), ("completed", "not-json")])
def test_incomplete_or_invalid_json_is_not_a_successful_completion(status, text):
    adapter = provider(lambda request: httpx.Response(200, json=response(text, status)))
    try:
        with pytest.raises(b.InvalidProviderResponse): b.complete(adapter, prompt({"type": "object"}))
    finally: adapter.close()


def test_sdk_timeout_is_sanitized_without_retries():
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("private endpoint details", request=request)
    adapter = provider(handler)
    try:
        with pytest.raises(b.ProviderTimeout) as caught: b.complete(adapter, prompt())
        assert len(calls) == 1 and "private" not in str(caught.value)
    finally: adapter.close()


def test_http_auth_failure_is_sanitized_and_not_retried():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(401, json={"error": {"message": "private API key details", "type": "authentication_error"}})
    adapter = provider(handler)
    try:
        with pytest.raises(b.ProviderUnavailable) as caught: b.complete(adapter, prompt())
        assert len(calls) == 1 and "private" not in str(caught.value)
    finally: adapter.close()


def test_refusal_and_unrequested_function_calls_are_not_accepted_as_text():
    refused = response()
    refused["output"][0]["content"] = [{"type": "refusal", "refusal": "refused"}]
    for value in (refused, {**response(), "output": [{"type": "function_call", "id": "call", "call_id": "call", "name": "execute", "arguments": "{}"}]}):
        adapter = provider(lambda request: httpx.Response(200, json=value))
        try:
            with pytest.raises(b.InvalidProviderResponse): b.complete(adapter, prompt())
        finally: adapter.close()


def test_embeddings_restored_to_input_order_and_duplicate_indexes_rejected():
    rows = [{"object": "embedding", "index": 1, "embedding": [0.5, 1.0]}, {"object": "embedding", "index": 0, "embedding": [1.0, 0.0]}]
    def handler(request):
        assert request.url.path == "/v1/embeddings"
        assert json.loads(request.content)["encoding_format"] == "float"
        return httpx.Response(200, json={"object": "list", "data": rows, "model": "configured-embedding", "usage": {"prompt_tokens": 2, "total_tokens": 2}})
    adapter = provider(handler)
    try:
        request = c.EmbeddingRequest(texts=("one", "two"))
        assert b.embed(adapter, request).vectors == ((1.0, 0.0), (0.5, 1.0))
        rows[0]["index"] = 0
        with pytest.raises(b.InvalidProviderResponse): b.embed(adapter, request)
    finally: adapter.close()
