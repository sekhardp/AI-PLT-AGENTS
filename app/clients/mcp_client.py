from __future__ import annotations

import asyncio
from typing import Any
import structlog
import httpx
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

logger = structlog.get_logger(__name__)


def _create_mcp_http_client(**kwargs) -> httpx.AsyncClient:
    """Create HTTPX AsyncClient that forces HTTPS on redirects for cloud-hosted services."""
    async def force_https_redirect_hook(request: httpx.Request) -> None:
        if request.url.scheme == "http" and request.url.host not in ("localhost", "127.0.0.1"):
            request.url = request.url.copy_with(scheme="https")

    headers = kwargs.get("headers")
    timeout = kwargs.get("timeout")
    auth = kwargs.get("auth")

    return httpx.AsyncClient(
        headers=headers,
        timeout=timeout if timeout is not None else httpx.Timeout(30.0, read=300.0),
        auth=auth,
        follow_redirects=True,
        event_hooks={"request": [force_https_redirect_hook]},
    )


class MCPRegistryClient:
    """Client for discovering and executing tools against the MCP Registry Gateway via SSE."""

    def __init__(self, registry_url: str, timeout_seconds: int = 60) -> None:
        self.registry_url = registry_url
        self.timeout_seconds = timeout_seconds

    async def list_tools(self) -> list[dict[str, Any]]:
        """Connect to the MCP Registry Gateway and retrieve all registered tools."""
        logger.info("mcp_discovering_tools", registry_url=self.registry_url)
        try:
            async with asyncio.timeout(self.timeout_seconds):
                async with sse_client(
                    url=self.registry_url,
                    httpx_client_factory=_create_mcp_http_client,
                ) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        tools_result = await session.list_tools()

                        tools = []
                        for tool in tools_result.tools:
                            schema = getattr(tool, "input_schema", getattr(tool, "inputSchema", {}))
                            if hasattr(schema, "model_dump"):
                                schema = schema.model_dump()
                            elif not isinstance(schema, dict):
                                schema = dict(schema) if schema else {}

                            tools.append({
                                "name": tool.name,
                                "description": tool.description or f"Tool: {tool.name}",
                                "input_schema": schema,
                            })
                        logger.info("mcp_tools_discovered", count=len(tools))
                        return tools
        except Exception as e:
            logger.warning(
                "mcp_tool_discovery_failed",
                registry_url=self.registry_url,
                error=str(e),
            )
            return []

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Connect to the MCP Registry Gateway and execute a specific tool."""
        logger.info("mcp_executing_tool", tool_name=tool_name, arguments=arguments)
        try:
            async with asyncio.timeout(self.timeout_seconds):
                async with sse_client(
                    url=self.registry_url,
                    httpx_client_factory=_create_mcp_http_client,
                ) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments)

                        if hasattr(result, "content") and result.content:
                            text_blocks = [
                                block.text
                                for block in result.content
                                if hasattr(block, "text") and block.text
                            ]
                            if text_blocks:
                                return "\n".join(text_blocks)
                        return str(result)
        except Exception as e:
            logger.error("mcp_tool_execution_failed", tool_name=tool_name, error=str(e))
            raise e
