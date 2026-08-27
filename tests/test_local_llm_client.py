import json

import httpx
import pytest
from app.clients.local_llm_client import LocalLLMClient


@pytest.mark.asyncio
async def test_local_llm_client_generate():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "Qwen/Qwen2.5-7B-Instruct"
        assert len(body["messages"]) == 2

        resp_payload = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "This is a local completion."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 8, "completion_tokens": 6, "total_tokens": 14},
        }
        return httpx.Response(200, json=resp_payload)

    client = LocalLLMClient(base_url="http://mock-vllm:8000/v1")
    # Swap out client transport with MockTransport
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://mock-vllm:8000/v1")

    res = await client.generate("Hello local model!", system_prompt="You are a helpful assistant.")
    assert res.content == "This is a local completion."
    assert res.provider == "local_vllm"
    assert res.model == "Qwen/Qwen2.5-7B-Instruct"
    assert res.usage["total_tokens"] == 14
    await client.aclose()


@pytest.mark.asyncio
async def test_local_llm_client_stream():
    def handler(request: httpx.Request) -> httpx.Response:
        lines = [
            'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n',
            'data: {"choices": [{"delta": {"content": " world!"}}]}\n\n',
            "data: [DONE]\n\n",
        ]
        return httpx.Response(200, content="".join(lines).encode("utf-8"))

    client = LocalLLMClient(base_url="http://mock-vllm:8000/v1")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://mock-vllm:8000/v1")

    tokens = []
    async for token in client.stream("Hello stream!"):
        tokens.append(token)

    assert "".join(tokens) == "Hello world!"
    await client.aclose()


@pytest.mark.asyncio
async def test_local_llm_client_liveness():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "Qwen/Qwen2.5-7B-Instruct"}]})
        return httpx.Response(404)

    client = LocalLLMClient(base_url="http://mock-vllm:8000/v1")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://mock-vllm:8000/v1")

    status = await client.check_liveness()
    assert status["status"] == "healthy"
    assert "Qwen/Qwen2.5-7B-Instruct" in status["available_models"]
    await client.aclose()
