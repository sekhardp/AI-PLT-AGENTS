from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from google import genai
from google.genai import types

from app.clients.base import BaseLLMClient, LLMResponse

logger = structlog.get_logger(__name__)


class GeminiClient(BaseLLMClient):
    """Production LLM client for Google Gemini models via Vertex AI using the Google GenAI SDK."""

    provider_name = "gemini"

    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        model_name: str = "gemini-2.5-flash",
        default_temperature: float = 0.7,
        default_max_tokens: int = 4096,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens

        self._client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
        )

        logger.info(
            "gemini_client_initialized",
            project_id=project_id,
            location=location,
            model_name=model_name,
        )

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate full completion using Gemini on Vertex AI."""
        temp = temperature if temperature is not None else self.default_temperature
        max_tok = max_tokens if max_tokens is not None else self.default_max_tokens

        config = types.GenerateContentConfig(
            temperature=temp,
            max_output_tokens=max_tok,
            system_instruction=system_prompt if system_prompt else None,
        )

        start = time.perf_counter()
        response = await self._client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        usage: dict[str, int] = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = {
                "prompt_tokens": getattr(um, "prompt_token_count", 0) or 0,
                "completion_tokens": getattr(um, "candidates_token_count", 0) or 0,
                "total_tokens": getattr(um, "total_token_count", 0) or 0,
            }

        content = response.text or ""

        logger.info(
            "gemini_generate_completed",
            model=self.model_name,
            latency_ms=round(latency_ms, 1),
            total_tokens=usage.get("total_tokens", 0),
        )

        return LLMResponse(
            content=content,
            model=self.model_name,
            provider=self.provider_name,
            usage=usage,
            latency_ms=latency_ms,
        )

    async def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens asynchronously from Gemini on Vertex AI."""
        temp = temperature if temperature is not None else self.default_temperature
        max_tok = max_tokens if max_tokens is not None else self.default_max_tokens

        config = types.GenerateContentConfig(
            temperature=temp,
            max_output_tokens=max_tok,
            system_instruction=system_prompt if system_prompt else None,
        )

        stream_response = await self._client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        async for chunk in stream_response:
            if chunk.text:
                yield chunk.text

    def health(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "project_id": self.project_id,
            "location": self.location,
            "status": "healthy",
        }
