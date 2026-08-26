from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


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
        yield

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
