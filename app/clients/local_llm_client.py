from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import structlog

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
        # Normalize base URL (ensure ends with /v1 for OpenAI compatibility)
        clean_url = base_url.rstrip("/")
        if not clean_url.endswith("/v1"):
            clean_url = f"{clean_url}/v1"

        self.base_url = clean_url
        self.model_name = model_name
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._headers = headers
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers,
            timeout=httpx.Timeout(float(timeout_seconds), connect=3.0),
        )

        logger.info(
            "local_llm_client_initialized",
            base_url=self.base_url,
            model_name=self.model_name,
            timeout_seconds=self.timeout_seconds,
        )

    def _build_messages(self, prompt: str, system_prompt: str | None = None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate full completion using local LLM instance via OpenAI-compatible endpoint."""
        temp = temperature if temperature is not None else self.default_temperature
        max_tok = max_tokens if max_tokens is not None else self.default_max_tokens

        payload = {
            "model": self.model_name,
            "messages": self._build_messages(prompt, system_prompt),
            "temperature": temp,
            "max_tokens": max_tok,
            "stream": False,
        }

        start = time.perf_counter()
        try:
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "local_llm_generate_failed",
                base_url=self.base_url,
                model=self.model_name,
                error=str(e),
                latency_ms=round(latency_ms, 1),
            )
            raise

        latency_ms = (time.perf_counter() - start) * 1000
        choices = data.get("choices", [])
        content = choices[0].get("message", {}).get("content", "") if choices else ""

        raw_usage = data.get("usage", {})
        usage = {
            "prompt_tokens": raw_usage.get("prompt_tokens", 0),
            "completion_tokens": raw_usage.get("completion_tokens", 0),
            "total_tokens": raw_usage.get("total_tokens", 0),
        }

        logger.info(
            "local_llm_generate_completed",
            model=self.model_name,
            latency_ms=round(latency_ms, 1),
            total_tokens=usage["total_tokens"],
        )

        return LLMResponse(
            content=content,
            model=self.model_name,
            provider=self.provider_name,
            usage=usage,
            latency_ms=latency_ms,
            metadata={"base_url": self.base_url},
        )

    async def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens asynchronously from local LLM instance via Server-Sent Events."""
        temp = temperature if temperature is not None else self.default_temperature
        max_tok = max_tokens if max_tokens is not None else self.default_max_tokens

        payload = {
            "model": self.model_name,
            "messages": self._build_messages(prompt, system_prompt),
            "temperature": temp,
            "max_tokens": max_tok,
            "stream": True,
        }

        try:
            async with self._client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    clean_line = line.strip()
                    if not clean_line or not clean_line.startswith("data:"):
                        continue
                    data_str = clean_line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            token = delta.get("content")
                            if token:
                                yield token
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error("local_llm_stream_failed", model=self.model_name, error=str(e))
            raise

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
        except Exception as e:  # noqa: BLE001
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
        """Close underlying httpx client."""
        await self._client.aclose()
