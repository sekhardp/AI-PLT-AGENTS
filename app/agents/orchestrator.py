from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ToolCallPart, ToolReturnPart

from app.agents.base import AgentResult, BaseAgent, extract_usage_dict, resolve_pydantic_model
from app.agents.deps import AgentDeps
from app.agents.mcp_tools import build_mcp_tools_from_definitions
from app.agents.registry import AgentRegistry
from app.clients.base import BaseLLMClient

logger = structlog.get_logger(__name__)

ORCHESTRATOR_SYSTEM_PROMPT = """You are the master AI Platform Orchestrator.
Your job is to assist the user by coordinating specialized tools and agents, or answering their queries directly with depth, clarity, and precision.

When specialized tools or domain agents are registered, evaluate whether the user prompt requires a tool/agent. If not, provide a comprehensive, accurate response directly.
"""


class OrchestratorAgent(BaseAgent):
    """Production Master Orchestrator Agent powered by Pydantic AI and MCP tool orchestration."""

    def __init__(self, registry: AgentRegistry, llm_client: BaseLLMClient) -> None:
        super().__init__(
            agent_id="orchestrator-01",
            name="Agent Orchestrator",
            description="Analyzes user intent, coordinates specialized MCP agents and tools, and synthesizes answers using Gemini.",
            capabilities=["routing", "task-decomposition", "mcp-orchestration", "synthesis"],
        )
        self.registry = registry
        self.llm_client = llm_client

    def _build_pydantic_agent(self, dynamic_tools: list[Any]) -> Agent[AgentDeps, str]:
        """Construct a configured Pydantic AI Agent instance with dynamic MCP tools and system prompts."""
        agent = Agent[AgentDeps, str](
            deps_type=AgentDeps,
            tools=dynamic_tools,
            retries=2,
        )

        @agent.system_prompt
        async def _system_prompt_builder(ctx: RunContext[AgentDeps]) -> str:
            parts = [ORCHESTRATOR_SYSTEM_PROMPT]

            ctx_items = []
            if ctx.deps.document_ids:
                ctx_items.append(f"- Active Document IDs: {ctx.deps.document_ids}")
            if ctx.deps.user_id:
                ctx_items.append(f"- User ID: {ctx.deps.user_id}")
            if ctx.deps.session_context:
                for k, v in ctx.deps.session_context.items():
                    if k not in ("chat_history", "routing_strategy", "document_id", "document_ids", "user_id", "prompt"):
                        ctx_items.append(f"- {k}: {v}")
            if ctx_items:
                parts.append("### Current Session Context:\n" + "\n".join(ctx_items))

            # Available Skills Directory (Compact Overview + load_skill instruction)
            skills_overview = ctx.deps.skill_registry.get_skills_overview()
            if skills_overview:
                parts.append(
                    f"### Available Skills Directory:\n"
                    f"{skills_overview}\n\n"
                    f"To view the full standard operating procedure, formatting guidelines, or schemas for any specialized skill above, invoke the `load_skill` tool with the skill name (e.g. `load_skill(skill_name='presentation-storytelling')`)."
                )

            return "\n\n".join(parts)

        return agent

    def _get_available_mcp_tools(self) -> list[dict[str, Any]]:
        """Retrieve all discovered MCP tool schemas from registered agents."""
        tools: list[dict[str, Any]] = []
        for a in self.registry.list_agents():
            if a.agent_id != self.agent_id:
                tool_name = getattr(a, "tool_name", None) or (a.capabilities[0] if a.capabilities else "mcp-tool")
                tool_schema = getattr(a, "tool_schema", None) or {}
                tools.append({
                    "name": tool_name,
                    "description": a.description,
                    "input_schema": tool_schema,
                })
        return tools

    def _get_mcp_client(self) -> Any:
        """Find the active MCP registry client from registered agents."""
        for a in self.registry.list_agents():
            client = getattr(a, "mcp_client", None)
            if client:
                return client
        return None

    async def execute(self, prompt: str, *, context: dict[str, Any] | None = None) -> AgentResult:
        """Execute user prompt with Pydantic AI agent loop and dynamic MCP tools."""
        logger.info("pydantic_ai_orchestrator_execute", prompt_preview=prompt[:80])
        start_time = time.perf_counter()

        target: str | None = None
        routing_reason: str | None = None
        complexity_score: float | None = None
        routing_strategy: str | None = context.get("routing_strategy") if context else None

        if hasattr(self.llm_client, "classify"):
            decision = self.llm_client.classify(prompt, strategy_override=routing_strategy, context=context)
            target = decision.target
            routing_reason = decision.reason
            complexity_score = decision.complexity_score
            routing_strategy = getattr(decision.strategy, "value", str(decision.strategy))

        selected_model = context.get("model") if context else None
        model = resolve_pydantic_model(self.llm_client, target=target, prompt=prompt, model_name=selected_model)
        deps = AgentDeps.from_context(mcp_client=self._get_mcp_client(), context=context, active_prompt=prompt)
        tool_defs = self._get_available_mcp_tools()
        dynamic_tools = build_mcp_tools_from_definitions(tool_defs)
        agent = self._build_pydantic_agent(dynamic_tools)

        try:
            result = await agent.run(
                prompt,
                deps=deps,
                model=model,
            )
            latency_ms = (time.perf_counter() - start_time) * 1000
            usage_dict = extract_usage_dict(result.usage)

            # Extract executed tools from all messages
            executed_tools: list[dict[str, Any]] = []
            for m in result.all_messages():
                for p in getattr(m, "parts", []):
                    if isinstance(p, ToolCallPart):
                        executed_tools.append({
                            "tool_name": p.tool_name,
                            "arguments": p.args if isinstance(p.args, dict) else {},
                        })
                    elif isinstance(p, ToolReturnPart):
                        if executed_tools and executed_tools[-1].get("tool_name") == p.tool_name:
                            executed_tools[-1]["result"] = str(p.content)

            model_name = getattr(model, "model_name", "pydantic-ai-model")
            metadata: dict[str, Any] = {
                "provider": getattr(self.llm_client, "provider_name", "pydantic_ai"),
                "model": model_name,
                "usage": usage_dict,
                "latency_ms": round(latency_ms, 1),
                "routed_to": target,
                "routing_reason": routing_reason,
                "complexity_score": complexity_score,
                "executed_tools": executed_tools,
            }
            if routing_strategy:
                metadata["routing_strategy"] = routing_strategy
            if context:
                for k, v in context.items():
                    if k not in metadata:
                        metadata[k] = v

            return AgentResult(
                content=result.output,
                agent_id=self.agent_id,
                agent_name=self.name,
                metadata=metadata,
            )
        except Exception as e:
            logger.error("pydantic_ai_orchestrator_run_failed", error=str(e))
            raise

    async def stream(
        self, prompt: str, *, context: dict[str, Any] | None = None
    ) -> AsyncGenerator[Any, None]:
        """Stream completion tokens and tool execution events dynamically using Pydantic AI run_stream."""
        target: str | None = None
        if hasattr(self.llm_client, "classify"):
            strategy_override = context.get("routing_strategy") if context else None
            decision = self.llm_client.classify(prompt, strategy_override=strategy_override, context=context)
            target = decision.target
            if context is not None:
                context["routed_to"] = target
                context["routing_reason"] = decision.reason

        selected_model = context.get("model") if context else None
        model = resolve_pydantic_model(self.llm_client, target=target, prompt=prompt, model_name=selected_model)
        
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        deps = AgentDeps.from_context(mcp_client=self._get_mcp_client(), context=context, event_queue=event_queue, active_prompt=prompt)
        tool_defs = self._get_available_mcp_tools()
        dynamic_tools = build_mcp_tools_from_definitions(tool_defs)
        agent = self._build_pydantic_agent(dynamic_tools)

        async def _run_stream_producer():
            try:
                async with agent.run_stream(
                    prompt,
                    deps=deps,
                    model=model,
                ) as stream_result:
                    async for token in stream_result.stream_text(delta=True):
                        await event_queue.put({"type": "token", "token": token})

                    if context is not None:
                        context["usage"] = extract_usage_dict(stream_result.usage)
            except Exception as e:
                logger.warning("pydantic_ai_stream_failed_falling_back", error=str(e))
                try:
                    async for token in self.llm_client.stream(prompt=prompt, context=context):
                        await event_queue.put({"type": "token", "token": token})
                except Exception as fb_err:
                    await event_queue.put({"type": "error", "error": str(fb_err)})
            finally:
                await event_queue.put({"type": "end"})

        producer_task = asyncio.create_task(_run_stream_producer())
        try:
            while True:
                event = await event_queue.get()
                if event.get("type") == "end":
                    break
                elif event.get("type") == "token":
                    yield event["token"]
                elif event.get("type") in ("tool_start", "tool_done", "step_update"):
                    yield event
                elif event.get("type") == "error":
                    yield "\n[Error: " + str(event.get("error", "Unknown error")) + "]"
        finally:
            if not producer_task.done():
                producer_task.cancel()
