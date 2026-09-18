from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import structlog
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google_cloud import GoogleCloudProvider

from app.agents.base import extract_usage_dict
from app.clients.base import BaseLLMClient, LLMResponse

logger = structlog.get_logger(__name__)


class GeminiClient(BaseLLMClient):
    """Production LLM client for Google Gemini models on Vertex AI powered by Pydantic AI."""

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

        self._provider = GoogleCloudProvider(project=project_id, location=location)
        self._model = GoogleModel(model_name, provider=self._provider)

        logger.info(
            "gemini_client_initialized",
            project_id=project_id,
            location=location,
            model_name=model_name,
        )

    def get_pydantic_model(self, model_name: str | None = None) -> GoogleModel:
        """Return the initialized Pydantic AI GoogleModel configured for Vertex AI."""
        if model_name and model_name not in ("frontier", "local") and model_name != self.model_name:
            return GoogleModel(model_name, provider=self._provider)
        return self._model

    def health(self) -> dict[str, Any]:
        """Return provider configuration and health status."""
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "project_id": self.project_id,
            "location": self.location,
            "status": "healthy",
        }

    async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Compatibility fallback to execute a single prompt generation via Pydantic AI."""
        agent = Agent(model=self._model)
        result = await agent.run(prompt)
        return LLMResponse(
            content=result.output,
            model=self.model_name,
            provider=self.provider_name,
            usage=extract_usage_dict(result.usage),
        )

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncGenerator[str, None]:
        """Compatibility fallback to stream tokens via Pydantic AI."""
        agent = Agent(model=self._model)
        async with agent.run_stream(prompt) as stream_result:
            async for token in stream_result.stream_text(delta=True):
                yield token
