from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import structlog

from app.agents.base import AgentResult, BaseAgent
from app.clients.base import BaseLLMClient
from app.clients.mcp_client import MCPRegistryClient
from app.core.skills import skill_registry

logger = structlog.get_logger(__name__)


class MCPAgent(BaseAgent):
    """Dynamic Agent that translates natural language prompts into MCP tool invocations using Gemini and Skill playbooks."""

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

    def _get_skill_instructions(self) -> str:
        """Retrieve attached SKILL.md playbook instructions if available for this tool."""
        skill = skill_registry.get_skill_for_tool(self.tool_name)
        if skill and "body" in skill:
            return f"\n\n### Attached Skill Workflow & SOP ({skill['name']}):\n{skill['body']}\n"
        return ""

    async def execute(self, prompt: str, *, context: dict[str, Any] | None = None) -> AgentResult:
        """Execute MCP tool invocation using native function calling and synthesis."""
        logger.info("mcp_agent_execute", agent_id=self.agent_id, tool_name=self.tool_name)

        chat_history: list[dict[str, Any]] = list(context.get("chat_history") or []) if context else []
        tool_def = [{
            "name": self.tool_name,
            "description": self.description,
            "input_schema": self.tool_schema,
        }]

        skill_prompt = self._get_skill_instructions()
        system_prompt = f"You are a specialized agent for tool '{self.tool_name}'. {skill_prompt}".strip()

        # Step 1: Native tool call determination by LLM
        resp = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            chat_history=chat_history,
            tools=tool_def,
            context=context,
        )

        arguments: dict[str, Any] = {}
        raw_tool_result = ""

        if resp.tool_calls:
            arguments = resp.tool_calls[0].arguments
            try:
                raw_tool_result = await self.mcp_client.call_tool(self.tool_name, arguments)
            except Exception as e:
                logger.error("mcp_tool_execution_error", tool_name=self.tool_name, error=str(e))
                return AgentResult(
                    content=f"Error executing tool '{self.tool_name}': {e!s}",
                    agent_id=self.agent_id,
                    agent_name=self.name,
                    metadata={"error": str(e), "tool_name": self.tool_name, "arguments": arguments},
                )

            chat_history.append({"role": "model", "tool_calls": resp.tool_calls})
            chat_history.append({
                "role": "tool",
                "name": self.tool_name,
                "tool_call_id": resp.tool_calls[0].id,
                "content": raw_tool_result,
            })

            # Step 2: Grounded synthesis turn
            synthesis_resp = await self.llm_client.generate(
                prompt="",
                system_prompt="You are an expert AI assistant providing insights, grounded answers, and summarizing tool results accurately.",
                chat_history=chat_history,
                context=context,
            )
            final_content = synthesis_resp.content
            model_name = synthesis_resp.model
            usage = synthesis_resp.usage
        else:
            final_content = resp.content
            model_name = resp.model
            usage = resp.usage

        return AgentResult(
            content=final_content,
            agent_id=self.agent_id,
            agent_name=self.name,
            metadata={
                "tool_name": self.tool_name,
                "arguments": arguments,
                "raw_result": raw_tool_result,
                "provider": self.llm_client.provider_name,
                "model": model_name,
                "usage": usage,
            },
        )

    async def stream(
        self, prompt: str, *, context: dict[str, Any] | None = None
    ) -> AsyncGenerator[str, None]:
        """Stream synthesized answer from tool execution respecting skill citation rules."""
        result = await self.execute(prompt, context=context)
        yield result.content
