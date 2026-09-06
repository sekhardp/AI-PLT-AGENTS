import httpx
import pytest
from app.clients.local_llm_client import LocalLLMClient
from pydantic_ai.models.test import TestModel


@pytest.mark.asyncio
async def test_local_llm_client_initialization_and_pydantic_model():
    client = LocalLLMClient(base_url="http://localhost:8000/v1", model_name="Qwen/Qwen2.5-7B-Instruct")
    model = client.get_pydantic_model()
    assert model is not None
    assert client.health()["status"] == "configured"
    assert client.health()["model"] == "Qwen/Qwen2.5-7B-Instruct"
    await client.aclose()


@pytest.mark.asyncio
async def test_local_llm_client_generate_and_stream():
    client = LocalLLMClient(base_url="http://localhost:8000/v1", model_name="Qwen/Qwen2.5-7B-Instruct")
    # Replace internal model with TestModel for offline unit testing
    client._model = TestModel(custom_output_text="This is a local completion.")

    res = await client.generate("Hello local model!", system_prompt="You are a helpful assistant.")
    assert res.content == "This is a local completion."
    assert res.provider == "local_vllm"
    assert res.model == "Qwen/Qwen2.5-7B-Instruct"
    assert res.usage["total_tokens"] > 0

    tokens = []
    async for token in client.stream("Hello stream!"):
        tokens.append(token)
    assert len(tokens) > 0

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
