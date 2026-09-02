from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import structlog

from app.agents.base import AgentResult, BaseAgent
from app.agents.registry import AgentRegistry
from app.clients.base import BaseLLMClient
from app.core.skills import skill_registry

logger = structlog.get_logger(__name__)

ORCHESTRATOR_SYSTEM_PROMPT = """You are the master AI Platform Orchestrator.
Your job is to assist the user by coordinating specialized tools and agents, or answering their queries directly with depth, clarity, and precision.

When specialized tools or domain agents are registered, evaluate whether the user prompt requires a tool/agent. If not, provide a comprehensive, accurate response directly.
"""


class OrchestratorAgent(BaseAgent):
    """Production Master Orchestrator Agent powered by native Model Context Protocol (MCP) tool execution."""

    def __init__(self, registry: AgentRegistry, llm_client: BaseLLMClient) -> None:
        super().__init__(
            agent_id="orchestrator-01",
            name="Agent Orchestrator",
            description="Analyzes user intent, coordinates specialized MCP agents and tools, and synthesizes answers using Gemini.",
            capabilities=["routing", "task-decomposition", "mcp-orchestration", "synthesis"],
        )
        self.registry = registry
        self.llm_client = llm_client

    def _get_available_mcp_tools(self) -> list[dict[str, Any]]:
        """Retrieve all discovered MCP tool schemas from registered agents."""
        tools: list[dict[str, Any]] = []
        for a in self.registry.list_agents():
            if a.agent_id != self.agent_id:
                tool_name = getattr(a, "tool_name", None) or a.capabilities[0]
                tool_schema = getattr(a, "tool_schema", None) or {}
                tools.append({
                    "name": tool_name,
                    "description": a.description,
                    "input_schema": tool_schema,
                })
        return tools

    async def _execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool against the registered MCP client."""
        for a in self.registry.list_agents():
            if getattr(a, "tool_name", None) == tool_name or a.agent_id == f"mcp-{tool_name}":
                mcp_client = getattr(a, "mcp_client", None)
                if mcp_client:
                    return await mcp_client.call_tool(tool_name, arguments)
        return f"Error: Tool '{tool_name}' not found."

    def _build_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        """Dynamically construct system prompt including user context, currently registered skills and operating guidelines."""
        parts = [ORCHESTRATOR_SYSTEM_PROMPT]

        if context:
            ctx_items = []
            if "document_id" in context:
                ctx_items.append(f"- Active Document ID: {context['document_id']}")
            elif "document_ids" in context:
                ctx_items.append(f"- Active Document IDs: {context['document_ids']}")
            if "user_id" in context:
                ctx_items.append(f"- User ID: {context['user_id']}")
            if ctx_items:
                parts.append("### Current Session Context:\n" + "\n".join(ctx_items))

        skills_summary = skill_registry.get_all_skills_instructions()
        if skills_summary:
            parts.append(f"### Standard Operating Procedures & Skills:\n{skills_summary}")

        return "\n\n".join(parts)

    async def execute(self, prompt: str, *, context: dict[str, Any] | None = None) -> AgentResult:
        """Execute user prompt with native tool calling loop and grounded answer synthesis."""
        logger.info("orchestrator_execute", prompt_preview=prompt[:80])
        tools = self._get_available_mcp_tools()
        system_prompt = self._build_system_prompt(context=context)
        chat_history: list[dict[str, Any]] = list(context.get("chat_history") or []) if context else []

        generate_kwargs: dict[str, Any] = {
            "prompt": prompt,
            "system_prompt": system_prompt,
            "chat_history": chat_history,
            "tools": tools if tools else None,
            "context": context,
        }
        if context and "routing_strategy" in context:
            generate_kwargs["strategy_override"] = context["routing_strategy"]

        response = await self.llm_client.generate(**generate_kwargs)
        executed_tools: list[dict[str, Any]] = []

        # Native Tool Execution Loop (supports multi-hop / multi-tool workflows)
        hop = 0
        while response.tool_calls and hop < 5:
            hop += 1
            current_calls = response.tool_calls
            chat_history.append({"role": "model", "tool_calls": current_calls})

            responses: list[dict[str, Any]] = []
            for tc in current_calls:
                logger.info("orchestrator_invoking_tool", tool_name=tc.name, arguments=tc.arguments)
                try:
                    raw_result = await self._execute_tool(tc.name, tc.arguments)
                except Exception as e:
                    raw_result = f"Error executing tool '{tc.name}': {e!s}"

                executed_tools.append({
                    "tool_name": tc.name,
                    "arguments": tc.arguments,
                    "result": raw_result,
                })
                responses.append({
                    "name": tc.name,
                    "tool_call_id": tc.id,
                    "content": raw_result,
                })

            chat_history.append({
                "role": "tool",
                "responses": responses,
            })

            response = await self.llm_client.generate(
                prompt="",
                system_prompt=system_prompt,
                chat_history=chat_history,
                tools=tools if tools else None,
                context=context,
            )

        exec_metadata = {
            "provider": response.provider,
            "model": response.model,
            "usage": response.usage,
            "latency_ms": response.latency_ms,
            "routed_to": response.metadata.get("routed_to"),
            "executed_tools": executed_tools,
        }
        exec_metadata.update(response.metadata)

        return AgentResult(
            content=response.content,
            agent_id=self.agent_id,
            agent_name=self.name,
            metadata=exec_metadata,
        )

    async def stream(
        self, prompt: str, *, context: dict[str, Any] | None = None
    ) -> AsyncGenerator[str, None]:
        """Stream response with native tool execution and token generation."""
        tools = self._get_available_mcp_tools()
        system_prompt = self._build_system_prompt(context=context)
        chat_history: list[dict[str, Any]] = list(context.get("chat_history") or []) if context else []

        # If tools exist, check if native tool calling is triggered
        if tools:
            generate_kwargs: dict[str, Any] = {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "chat_history": chat_history,
                "tools": tools,
                "context": context,
            }
            if context and "routing_strategy" in context:
                generate_kwargs["strategy_override"] = context["routing_strategy"]

            response = await self.llm_client.generate(**generate_kwargs)

            # If tool calls are requested, execute them first before streaming synthesis
            if response.tool_calls:
                chat_history.append({"role": "model", "tool_calls": response.tool_calls})
                responses: list[dict[str, Any]] = []
                for tc in response.tool_calls:
                    logger.info("orchestrator_streaming_invoking_tool", tool_name=tc.name, arguments=tc.arguments)
                    try:
                        raw_result = await self._execute_tool(tc.name, tc.arguments)
                    except Exception as e:
                        raw_result = f"Error executing tool '{tc.name}': {e!s}"

                    responses.append({
                        "name": tc.name,
                        "tool_call_id": tc.id,
                        "content": raw_result,
                    })

                chat_history.append({
                    "role": "tool",
                    "responses": responses,
                })

                # Stream synthesis from tool results
                stream_kwargs: dict[str, Any] = {
                    "prompt": "",
                    "system_prompt": system_prompt,
                    "chat_history": chat_history,
                    "context": context,
                }
                async for token in self.llm_client.stream(**stream_kwargs):
                    yield token
                return

        # Direct streaming without tool calls
        stream_kwargs = {
            "prompt": prompt,
            "system_prompt": system_prompt,
            "chat_history": chat_history,
            "context": context,
        }
        if context and "routing_strategy" in context:
            stream_kwargs["strategy_override"] = context["routing_strategy"]

        async for token in self.llm_client.stream(**stream_kwargs):
            yield token
