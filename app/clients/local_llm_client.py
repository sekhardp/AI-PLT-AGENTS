from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import structlog
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.agents.base import extract_usage_dict
from app.clients.base import BaseLLMClient, LLMResponse

logger = structlog.get_logger(__name__)



class LocalLLMClient(BaseLLMClient):
    """Production client for local and self-hosted LLMs exposing an OpenAI-compatible API (vLLM, Ollama, TGI)."""

    provider_name = "local_vllm"

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model_name: str = "Qwen/Qwen2.5-7B-Instruct",
        api_key: str | None = None,
        timeout_seconds: int = 60,
        default_temperature: float = 0.7,
        default_max_tokens: int = 4096,
    ) -> None:
        clean_url = base_url.rstrip("/")
        if not clean_url.endswith("/v1"):
            clean_url = f"{clean_url}/v1"

        self.base_url = clean_url
        self.model_name = model_name
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens

        headers: dict[str, str] = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(float(timeout_seconds), connect=3.0),
        )
        from openai import AsyncOpenAI

        self._openai_client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=api_key or "local-key",
            http_client=self._client,
            max_retries=0,
        )
        self._provider = OpenAIProvider(
            openai_client=self._openai_client,
        )

        self._model = OpenAIChatModel(model_name, provider=self._provider)



        logger.info(
            "local_llm_client_initialized",
            base_url=self.base_url,
            model_name=self.model_name,
            timeout_seconds=self.timeout_seconds,
        )

    def get_pydantic_model(self) -> OpenAIChatModel:
        """Return the initialized Pydantic AI OpenAIChatModel."""
        return self._model

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate response using Pydantic AI OpenAIChatModel."""
        agent = Agent(model=self._model, system_prompt=system_prompt or "")
        start = time.perf_counter()
        result = await agent.run(prompt)
        latency_ms = (time.perf_counter() - start) * 1000

        return LLMResponse(
            content=result.output,
            model=self.model_name,
            provider=self.provider_name,
            usage=extract_usage_dict(result.usage),
            latency_ms=latency_ms,
            metadata={"base_url": self.base_url},
        )

    async def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens using Pydantic AI OpenAIChatModel."""
        agent = Agent(model=self._model, system_prompt=system_prompt or "")
        async with agent.run_stream(prompt) as stream_result:
            async for token in stream_result.stream_text(delta=True):
                yield token


    def health(self) -> dict[str, Any]:
        """Return provider configuration info."""
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "base_url": self.base_url,
            "status": "configured",
        }

    async def check_liveness(self) -> dict[str, Any]:
        """Check real-time network liveness and inspect active models on the local LLM instance."""
        start = time.perf_counter()
        try:
            response = await self._client.get("/models", timeout=3.0)
            latency_ms = (time.perf_counter() - start) * 1000
            if response.status_code == 200:
                data = response.json()
                available_models = [m.get("id") for m in data.get("data", [])]
                return {
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "base_url": self.base_url,
                    "status": "healthy",
                    "latency_ms": round(latency_ms, 1),
                    "available_models": available_models,
                }
            return {
                "provider": self.provider_name,
                "model": self.model_name,
                "base_url": self.base_url,
                "status": f"unhealthy_status_{response.status_code}",
                "latency_ms": round(latency_ms, 1),
            }
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return {
                "provider": self.provider_name,
                "model": self.model_name,
                "base_url": self.base_url,
                "status": "unreachable",
                "latency_ms": round(latency_ms, 1),
                "error": str(e),
            }

    async def aclose(self) -> None:
        """Close underlying HTTP client."""
        await self._client.aclose()
