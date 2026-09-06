from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ToolCallPart, ToolReturnPart

from app.agents.base import AgentResult, BaseAgent, extract_usage_dict, resolve_pydantic_model
from app.agents.deps import AgentDeps
from app.agents.mcp_tools import create_mcp_tool
from app.clients.base import BaseLLMClient
from app.clients.mcp_client import MCPRegistryClient
from app.core.skills import skill_registry

logger = structlog.get_logger(__name__)


class MCPAgent(BaseAgent):
    """Dynamic Agent that translates natural language prompts into MCP tool invocations using Pydantic AI and Skill playbooks."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        tool_name: str,
        tool_schema: dict[str, Any],
        mcp_client: MCPRegistryClient,
        llm_client: BaseLLMClient,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            capabilities=[tool_name, "mcp-tool"],
        )
        self.tool_name = tool_name
        self.tool_schema = tool_schema
        self.mcp_client = mcp_client
        self.llm_client = llm_client

    def _build_pydantic_agent(self, tool: Any) -> Agent[AgentDeps, str]:
        agent = Agent[AgentDeps, str](
            deps_type=AgentDeps,
            tools=[tool],
            retries=2,
        )

        @agent.system_prompt
        async def _system_prompt_builder(ctx: RunContext[AgentDeps]) -> str:
            skill = skill_registry.get_skill_for_tool(self.tool_name)
            skill_text = (
                f"\n\n### Attached Skill Workflow & SOP ({skill['name']}):\n{skill['body']}\n"
                if skill and "body" in skill
                else ""
            )
            return f"You are a specialized agent for tool '{self.tool_name}'. {skill_text}".strip()

        return agent

    async def execute(self, prompt: str, *, context: dict[str, Any] | None = None) -> AgentResult:
        """Execute MCP tool invocation using Pydantic AI and synthesis."""
        logger.info("mcp_agent_execute", agent_id=self.agent_id, tool_name=self.tool_name)
        start_time = time.perf_counter()

        deps = AgentDeps.from_context(mcp_client=self.mcp_client, context=context)
        tool = create_mcp_tool(self.tool_name, self.description, self.tool_schema)
        model = resolve_pydantic_model(self.llm_client, prompt=prompt)
        agent = self._build_pydantic_agent(tool)

        try:
            result = await agent.run(
                prompt,
                deps=deps,
                model=model,
            )
            latency_ms = (time.perf_counter() - start_time) * 1000
            usage_dict = extract_usage_dict(result.usage)

            raw_result = ""
            arguments: dict[str, Any] = {}
            for m in result.all_messages():
                for p in getattr(m, "parts", []):
                    if isinstance(p, ToolCallPart) and p.tool_name == self.tool_name:
                        arguments = p.args if isinstance(p.args, dict) else {}
                    elif isinstance(p, ToolReturnPart) and p.tool_name == self.tool_name:
                        raw_result = str(p.content)

            return AgentResult(
                content=result.output,
                agent_id=self.agent_id,
                agent_name=self.name,
                metadata={
                    "tool_name": self.tool_name,
                    "arguments": arguments,
                    "raw_result": raw_result,
                    "provider": getattr(self.llm_client, "provider_name", "pydantic_ai"),
                    "model": getattr(model, "model_name", "pydantic-ai-model"),
                    "usage": usage_dict,
                    "latency_ms": round(latency_ms, 1),
                },
            )
        except Exception as e:
            logger.error("mcp_agent_pydantic_run_failed", error=str(e))
            raise

    async def stream(
        self, prompt: str, *, context: dict[str, Any] | None = None
    ) -> AsyncGenerator[str, None]:
        """Stream synthesized answer from tool execution respecting skill citation rules."""
        result = await self.execute(prompt, context=context)
        yield result.content

