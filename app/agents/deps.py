from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.clients.mcp_client import MCPRegistryClient
from app.core.skills import SkillRegistry, skill_registry


@dataclass
class AgentDeps:
    """Type-safe dependency container for Pydantic AI Agent runs and system prompt injection."""

    mcp_client: MCPRegistryClient | None = None
    skill_registry: SkillRegistry = field(default_factory=lambda: skill_registry)
    user_id: str | None = None
    document_ids: list[str] = field(default_factory=list)
    session_context: dict[str, Any] = field(default_factory=dict)
    event_queue: asyncio.Queue[dict[str, Any]] | None = None

    @classmethod
    def from_context(
        cls,
        mcp_client: MCPRegistryClient | None = None,
        context: dict[str, Any] | None = None,
        registry: SkillRegistry | None = None,
        event_queue: asyncio.Queue[dict[str, Any]] | None = None,
    ) -> AgentDeps:
        """Construct AgentDeps from a runtime execution context dictionary."""
        ctx = context or {}
        doc_ids: list[str] = []
        if "document_ids" in ctx:
            doc_ids = list(ctx["document_ids"])
        elif "document_id" in ctx:
            doc_ids = [ctx["document_id"]]

        return cls(
            mcp_client=mcp_client,
            skill_registry=registry or skill_registry,
            user_id=ctx.get("user_id"),
            document_ids=doc_ids,
            session_context=ctx,
            event_queue=event_queue,
        )
