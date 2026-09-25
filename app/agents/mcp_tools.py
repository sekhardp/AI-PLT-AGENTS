from __future__ import annotations

import contextlib
import time
import uuid
from typing import Any

import logfire
import structlog
from pydantic_ai import RunContext, Tool

from app.agents.deps import AgentDeps

logger = structlog.get_logger(__name__)


def create_mcp_tool(
    tool_name: str,
    description: str,
    tool_schema: dict[str, Any] | None = None,
) -> Tool[AgentDeps]:
    """Create a dynamic Pydantic AI Tool instance for an MCP tool with full Logfire span tracing."""

    async def _execute_mcp_tool(ctx: RunContext[AgentDeps], **kwargs: Any) -> str:
        logger.info("pydantic_ai_mcp_tool_invoked", tool_name=tool_name, arguments=kwargs)
        t0 = time.perf_counter()
        call_id = f"{tool_name}_{str(uuid.uuid4())[:6]}"

        with logfire.span("Tool: {tool_name}", tool_name=tool_name, arguments=kwargs) as span:
            if ctx.deps and ctx.deps.event_queue:
                with contextlib.suppress(Exception):
                    await ctx.deps.event_queue.put({
                        "type": "tool_start",
                        "id": call_id,
                        "tool_name": tool_name,
                        "arguments": kwargs,
                    })

            # 1. Check if tool requires a skill that hasn't been loaded yet
            if ctx.deps and ctx.deps.skill_registry and tool_name != "load_skill":
                required_skill = ctx.deps.skill_registry.get_skill_for_tool(tool_name)
                if required_skill:
                    req_skill_name = required_skill["name"]
                    if req_skill_name not in ctx.deps.loaded_skills:
                        err_msg = (
                            f"PROTOCOL ENFORCEMENT: Tool '{tool_name}' requires the '{req_skill_name}' skill playbook. "
                            f"You MUST call `load_skill(skill_name='{req_skill_name}')` first to inspect the ground-truth "
                            f"schemas, column definitions, and SOP rules before executing '{tool_name}'."
                        )
                        logger.warning(
                            "mcp_tool_execution_gated_skill_required",
                            tool_name=tool_name,
                            required_skill=req_skill_name,
                        )
                        span.set_attribute("status", "blocked_skill_not_loaded")
                        span.set_attribute("error", err_msg)
                        if ctx.deps and ctx.deps.event_queue:
                            with contextlib.suppress(Exception):
                                await ctx.deps.event_queue.put({
                                    "type": "tool_done",
                                    "id": call_id,
                                    "tool_name": tool_name,
                                    "status": "error",
                                    "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
                                    "error": err_msg,
                                })
                        return err_msg

            if not ctx.deps or not ctx.deps.mcp_client:
                err_msg = f"Error: MCP client is not configured for tool '{tool_name}'."
                logger.error("mcp_client_missing", tool_name=tool_name)
                span.set_attribute("status", "error")
                span.set_attribute("error", err_msg)
                if ctx.deps and ctx.deps.event_queue:
                    with contextlib.suppress(Exception):
                        await ctx.deps.event_queue.put({
                            "type": "tool_done",
                            "id": call_id,
                            "tool_name": tool_name,
                            "status": "error",
                            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
                            "error": err_msg,
                        })
                return err_msg

            try:
                raw_result = await ctx.deps.mcp_client.call_tool(tool_name, kwargs)
                duration_ms = round((time.perf_counter() - t0) * 1000, 1)

                span.set_attribute("status", "success")
                span.set_attribute("duration_ms", duration_ms)
                span.set_attribute("response", str(raw_result)[:4000] if raw_result is not None else None)

                if ctx.deps and ctx.deps.event_queue:
                    with contextlib.suppress(Exception):
                        await ctx.deps.event_queue.put({
                            "type": "tool_done",
                            "id": call_id,
                            "tool_name": tool_name,
                            "status": "success",
                            "duration_ms": duration_ms,
                            "result_preview": str(raw_result)[:300] if raw_result is not None else None,
                        })
                return str(raw_result)
            except Exception as e:
                duration_ms = round((time.perf_counter() - t0) * 1000, 1)
                logger.error("mcp_tool_execution_failed", tool_name=tool_name, error=str(e))

                span.record_exception(e)
                span.set_attribute("status", "error")
                span.set_attribute("duration_ms", duration_ms)
                span.set_attribute("error", str(e))

                if ctx.deps and ctx.deps.event_queue:
                    with contextlib.suppress(Exception):
                        await ctx.deps.event_queue.put({
                            "type": "tool_done",
                            "id": call_id,
                            "tool_name": tool_name,
                            "status": "error",
                            "duration_ms": duration_ms,
                            "error": str(e),
                        })
                return f"Error executing tool '{tool_name}': {e!s}"

    desc = description or f"MCP Tool: {tool_name}"
    if tool_schema and isinstance(tool_schema, dict) and (tool_schema.get("properties") or tool_schema.get("type") == "object"):
        schema_copy = dict(tool_schema)
        if "type" not in schema_copy:
            schema_copy["type"] = "object"
        return Tool.from_schema(
            _execute_mcp_tool,
            name=tool_name,
            description=desc,
            json_schema=schema_copy,
            takes_ctx=True,
        )
    return Tool(
        _execute_mcp_tool,
        name=tool_name,
        description=desc,
        takes_ctx=True,
    )


def create_load_skill_tool() -> Tool[AgentDeps]:
    """Create a Pydantic AI Tool allowing the LLM to dynamically inspect and load SKILL.md playbooks on-demand."""

    async def load_skill(ctx: RunContext[AgentDeps], skill_name: str) -> str:
        """Load the full standard operating procedure (SOP), guidelines, and schema rules for a specific skill from the Available Skills Directory."""
        logger.info("llm_loading_skill_dynamically", skill_name=skill_name)
        if not ctx.deps or not ctx.deps.skill_registry:
            return f"Error: Skill registry is not available to load '{skill_name}'."

        skill = ctx.deps.skill_registry.get_skill(skill_name)
        if not skill:
            # Fuzzy match by normalized name
            clean_target = skill_name.lower().replace("_", "-")
            for s_name, data in ctx.deps.skill_registry._skills.items():
                if clean_target in s_name.lower() or s_name.lower() in clean_target:
                    skill = data
                    break

        if not skill:
            available = list(ctx.deps.skill_registry._skills.keys())
            return f"Error: Skill '{skill_name}' not found. Available skills in directory: {available}"

        # Record skill as loaded in active session dependencies
        if ctx.deps:
            ctx.deps.loaded_skills.add(skill["name"])

        return f"# Skill Playbook: {skill['name']}\n\nDescription: {skill.get('description', '')}\n\n{skill.get('body', '')}"

    return Tool(
        load_skill,
        name="load_skill",
        description="PRIORITY TOOL - CALL FIRST: Load the full standard operating procedure (SOP), workflow guidelines, and ground-truth schemas for a specific skill from the Available Skills Directory before executing any domain queries (e.g. 'sales-products-analytics', 'presentation-storytelling', 'rag-knowledge-base').",
        takes_ctx=True,
    )


def build_mcp_tools_from_definitions(
    tool_definitions: list[dict[str, Any]],
    include_skill_loader: bool = True,
) -> list[Tool[AgentDeps]]:
    """Convert a list of MCP tool definition dictionaries into Pydantic AI Tool instances."""
    from app.core.skills import skill_registry

    tools: list[Tool[AgentDeps]] = []
    if include_skill_loader:
        tools.append(create_load_skill_tool())

    for tool_def in tool_definitions:
        name = tool_def.get("name")
        if not name:
            continue
        description = tool_def.get("description", f"Tool {name}")
        schema = tool_def.get("input_schema") or tool_def.get("parameters") or {}

        # Annotate description if tool requires a skill
        required_skill = skill_registry.get_skill_for_tool(name)
        if required_skill:
            req_name = required_skill["name"]
            description = f"[REQUIRES SKILL: '{req_name}'] (Must call load_skill('{req_name}') before invoking) {description}"

        tools.append(create_mcp_tool(name, description, schema))
    return tools
