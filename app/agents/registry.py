from __future__ import annotations

import structlog

from app.agents.base import BaseAgent

logger = structlog.get_logger(__name__)


class AgentRegistry:
    """Thread-safe, in-memory agent registry for dynamic registration and capability discovery."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent instance. Overwrites if agent_id exists."""
        self._agents[agent.agent_id] = agent
        logger.info("agent_registered", agent_id=agent.agent_id, name=agent.name)

    def unregister(self, agent_id: str) -> bool:
        """Remove an agent by ID."""
        removed = self._agents.pop(agent_id, None)
        if removed:
            logger.info("agent_unregistered", agent_id=agent_id)
        return removed is not None

    def get(self, agent_id: str) -> BaseAgent | None:
        """Look up an agent by ID."""
        return self._agents.get(agent_id)

    def list_agents(self) -> list[BaseAgent]:
        """Return all registered agents."""
        return list(self._agents.values())

    def get_by_capability(self, capability: str) -> list[BaseAgent]:
        """Find agents that advertise a specific capability."""
        return [a for a in self._agents.values() if capability in a.capabilities]

    def get_by_name(self, name: str) -> BaseAgent | None:
        """Find the first agent matching a name (case-insensitive)."""
        name_lower = name.lower()
        for agent in self._agents.values():
            if agent.name.lower() == name_lower:
                return agent
        return None

    @property
    def count(self) -> int:
        return len(self._agents)

    def health(self) -> dict:
        """Aggregate health of all registered agents."""
        return {
            "total_agents": self.count,
            "agents": [a.health() for a in self._agents.values()],
        }
