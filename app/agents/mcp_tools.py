from __future__ import annotations

from typing import Any

import structlog
from pydantic_ai import RunContext, Tool

from app.agents.deps import AgentDeps

logger = structlog.get_logger(__name__)


def create_mcp_tool(
    tool_name: str,
    description: str,
    tool_schema: dict[str, Any] | None = None,
) -> Tool[AgentDeps]:
    """Create a dynamic Pydantic AI Tool instance for an MCP tool."""

    async def _execute_mcp_tool(ctx: RunContext[AgentDeps], **kwargs: Any) -> str:
        logger.info("pydantic_ai_mcp_tool_invoked", tool_name=tool_name, arguments=kwargs)
        if not ctx.deps or not ctx.deps.mcp_client:
            err_msg = f"Error: MCP client is not configured for tool '{tool_name}'."
            logger.error("mcp_client_missing", tool_name=tool_name)
            return err_msg

        try:
            raw_result = await ctx.deps.mcp_client.call_tool(tool_name, kwargs)
            return str(raw_result)
        except Exception as e:
            logger.error("mcp_tool_execution_failed", tool_name=tool_name, error=str(e))
            return f"Error executing tool '{tool_name}': {e!s}"

    desc = description or f"MCP Tool: {tool_name}"
    return Tool(
        _execute_mcp_tool,
        name=tool_name,
        description=desc,
        takes_ctx=True,
    )


def build_mcp_tools_from_definitions(
    tool_definitions: list[dict[str, Any]],
) -> list[Tool[AgentDeps]]:
    """Convert a list of MCP tool definition dictionaries into Pydantic AI Tool instances."""
    tools: list[Tool[AgentDeps]] = []
    for tool_def in tool_definitions:
        name = tool_def.get("name")
        if not name:
            continue
        description = tool_def.get("description", f"Tool {name}")
        schema = tool_def.get("input_schema") or tool_def.get("parameters") or {}
        tools.append(create_mcp_tool(name, description, schema))
    return tools
