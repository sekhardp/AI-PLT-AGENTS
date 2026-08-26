from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import structlog

from app.agents.base import AgentResult, BaseAgent
from app.agents.registry import AgentRegistry
from app.clients.base import BaseLLMClient

logger = structlog.get_logger(__name__)

ORCHESTRATOR_SYSTEM_PROMPT = """You are the master AI Platform Orchestrator.
Your job is to assist the user by coordinating specialized tools and agents, or answering their queries directly with depth, clarity, and precision.

When specialized tools or domain agents are registered, evaluate whether the user prompt requires a tool/agent. If not, provide a comprehensive, accurate response directly.
"""


class OrchestratorAgent(BaseAgent):
    """Production Orchestrator Agent powered by Google Gemini for intelligent intent routing and multi-agent execution."""

    def __init__(self, registry: AgentRegistry, llm_client: BaseLLMClient) -> None:
        super().__init__(
            agent_id="orchestrator-01",
            name="Agent Orchestrator",
            description="Analyzes user intent, coordinates specialized MCP agents and tools, and synthesizes answers using Gemini.",
            capabilities=["routing", "task-decomposition", "mcp-orchestration", "synthesis"],
        )
        self.registry = registry
        self.llm_client = llm_client

    async def _select_delegate_agent(self, prompt: str) -> BaseAgent | None:
        """Uses real LLM classification to select the best specialized agent or None if general query."""
        available_agents = [
            a for a in self.registry.list_agents() if a.agent_id != self.agent_id
        ]

        if not available_agents:
            return None

        agent_manifest = [
            {
                "agent_id": a.agent_id,
                "name": a.name,
                "description": a.description,
                "capabilities": a.capabilities,
            }
            for a in available_agents
        ]

        routing_system_prompt = (
            "You are a routing dispatcher. Given a user query and a list of available agents/tools, "
            "determine if the user query is asking for a specific tool or agent capability.\n\n"
            f"Available Agents:\n{json.dumps(agent_manifest, indent=2)}\n\n"
            "Rules:\n"
            "- If the query matches an agent or tool capability (e.g. weather, bigquery, database, tool execution), "
            "output ONLY a JSON object with: {\"selected_agent_id\": \"<agent_id>\", \"reason\": \"<reason>\"}\n"
            "- If the query is a general conversation, explanation, coding, or greeting, output: {\"selected_agent_id\": null, \"reason\": \"general_query\"}\n"
            "Output JSON ONLY. No markdown."
        )

        try:
            resp = await self.llm_client.generate(
                prompt=prompt,
                system_prompt=routing_system_prompt,
                temperature=0.1,
            )

            cleaned_text = resp.content.strip()
            if cleaned_text.startswith("```"):
                lines = cleaned_text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned_text = "\n".join(lines).strip()

            data = json.loads(cleaned_text)
            selected_id = data.get("selected_agent_id")
            if selected_id:
                agent = self.registry.get(selected_id)
                if agent:
                    logger.info("orchestrator_delegating", to_agent=agent.agent_id, reason=data.get("reason"))
                    return agent
        except Exception as e:
            logger.warning("orchestrator_routing_classification_failed", error=str(e))

        return None

    def _build_system_prompt(self) -> str:
        """Dynamically construct system prompt including currently registered tools."""
        available_agents = [
            a for a in self.registry.list_agents() if a.agent_id != self.agent_id
        ]
        if not available_agents:
            return ORCHESTRATOR_SYSTEM_PROMPT

        tools_list = "\n".join(
            f"- {a.name} (id: {a.agent_id}): {a.description}" for a in available_agents
        )
        return (
            f"{ORCHESTRATOR_SYSTEM_PROMPT}\n\n"
            f"You have access to the following specialized tools and agents:\n{tools_list}\n\n"
            "If the user asks what tools, MCP servers, or capabilities you have, enumerate them clearly based on this list."
        )

    async def execute(self, prompt: str, *, context: dict[str, Any] | None = None) -> AgentResult:
        """Route to specialized agent or execute directly using Gemini LLM."""
        delegate = await self._select_delegate_agent(prompt)

        if delegate:
            result = await delegate.execute(prompt, context=context)
            result.metadata["routed_by"] = self.agent_id
            return result

        # Direct Orchestrator Gemini execution
        logger.info("orchestrator_direct_generation", prompt_preview=prompt[:80])
        response = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=self._build_system_prompt(),
        )

        return AgentResult(
            content=response.content,
            agent_id=self.agent_id,
            agent_name=self.name,
            metadata={
                "provider": self.llm_client.provider_name,
                "model": response.model,
                "usage": response.usage,
                "latency_ms": response.latency_ms,
                "routed_to": None,
            },
        )

    async def stream(
        self, prompt: str, *, context: dict[str, Any] | None = None
    ) -> AsyncGenerator[str, None]:
        """Route and stream from delegate agent or stream directly from Gemini LLM."""
        delegate = await self._select_delegate_agent(prompt)

        if delegate:
            async for token in delegate.stream(prompt, context=context):
                yield token
            return

        logger.info("orchestrator_direct_streaming", prompt_preview=prompt[:80])
        async for token in self.llm_client.stream(
            prompt=prompt,
            system_prompt=self._build_system_prompt(),
        ):
            yield token
