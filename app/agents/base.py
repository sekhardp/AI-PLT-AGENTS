from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def extract_usage_dict(usage: Any) -> dict[str, int]:
    """Extract a standard usage dictionary from Pydantic AI RunResult usage."""
    if not usage:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return {
        "prompt_tokens": getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }


def resolve_pydantic_model(llm_client: Any, target: str | None = None, prompt: str = "", model_name: str | None = None) -> Any:
    """Resolve the appropriate Pydantic AI Model instance from an LLM client or fallback bridge."""
    # 1. Check if LLM client provides get_pydantic_model
    if hasattr(llm_client, "get_pydantic_model"):
        try:
            if hasattr(llm_client, "router"):
                model = llm_client.get_pydantic_model(target or "frontier", model_name=model_name)
                if model is not None:
                    return model
            else:
                clean_model_name = model_name if model_name not in ("frontier", "local") else None
                model = llm_client.get_pydantic_model(model_name=clean_model_name)
                if model is not None:
                    return model
        except TypeError:
            try:
                model = llm_client.get_pydantic_model()
                if model is not None:
                    return model
            except Exception:
                pass

    # 2. Check if client is already a Pydantic AI Model
    from pydantic_ai.models import Model

    if isinstance(llm_client, Model):
        return llm_client

    # 3. Fallback bridge using FunctionModel for mock/custom clients
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
    from pydantic_ai.models.function import FunctionModel

    async def _bridge_fn(messages: list[Any], info: Any) -> ModelResponse:
        tools_list = [{"name": t.name, "description": t.description} for t in getattr(info, "function_tools", [])]
        has_tool_return = any(
            isinstance(part, ToolReturnPart)
            for m in messages
            for part in getattr(m, "parts", [])
        )
        chat_history = [{"role": "tool"}] if has_tool_return else []

        resp = await llm_client.generate(
            prompt=prompt,
            tools=tools_list if tools_list else None,
            chat_history=chat_history,
        )
        if resp.tool_calls and not has_tool_return:
            parts: list[Any] = [
                ToolCallPart(tc.name, tc.arguments) for tc in resp.tool_calls
            ]
            return ModelResponse(parts=parts)
        return ModelResponse(parts=[TextPart(resp.content)])

    async def _bridge_stream(messages: list[Any], info: Any) -> AsyncGenerator[str, None]:
        async for chunk in llm_client.stream(prompt=prompt):
            yield chunk

    return FunctionModel(_bridge_fn, stream_function=_bridge_stream)


@dataclass
class AgentResult:
    """Standardized response from any agent execution."""

    content: str
    agent_id: str
    agent_name: str
    metadata: dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class BaseAgent(ABC):
    """Abstract base class for all agents in the framework."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        capabilities: list[str] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.capabilities: list[str] = capabilities or []

    @abstractmethod
    async def execute(self, prompt: str, *, context: dict[str, Any] | None = None) -> AgentResult:
        """Execute a prompt and return a complete AgentResult."""
        ...

    @abstractmethod
    async def stream(
        self, prompt: str, *, context: dict[str, Any] | None = None
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens asynchronously."""
        ...

    def health(self) -> dict[str, Any]:
        """Return health status of the agent."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "status": "healthy",
        }

    def info(self) -> dict[str, Any]:
        """Return agent metadata for API discovery."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "status": "active",
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.agent_id!r} name={self.name!r}>"
