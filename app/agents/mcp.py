from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import structlog

from app.agents.base import AgentResult, BaseAgent
from app.clients.base import BaseLLMClient
from app.clients.mcp_client import MCPRegistryClient

logger = structlog.get_logger(__name__)


class MCPAgent(BaseAgent):
    """Dynamic Agent that translates natural language prompts into MCP tool invocations using Gemini."""

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

    async def _extract_tool_arguments(self, prompt: str) -> dict[str, Any]:
        """Uses real LLM to extract JSON arguments from user prompt matching the tool's JSON schema."""
        extraction_system_prompt = (
            f"You are a structured parameter extractor for the tool '{self.tool_name}'.\n"
            f"Tool Description: {self.description}\n"
            f"Tool JSON Schema:\n{json.dumps(self.tool_schema, indent=2)}\n\n"
            "Analyze the user query and output ONLY a valid JSON object representing the tool arguments.\n"
            "Do not include markdown codeblocks or explanation. Output valid JSON only."
        )

        resp = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=extraction_system_prompt,
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

        try:
            return json.loads(cleaned_text)
        except Exception as e:
            logger.warning(
                "mcp_argument_json_parse_failed",
                tool_name=self.tool_name,
                raw=cleaned_text,
                error=str(e),
            )
            return {}

    async def execute(self, prompt: str, *, context: dict[str, Any] | None = None) -> AgentResult:
        """Extract arguments, execute MCP tool against registry gateway, and synthesize final answer."""
        logger.info("mcp_agent_execute", agent_id=self.agent_id, tool_name=self.tool_name)

        arguments = await self._extract_tool_arguments(prompt)

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

        # Synthesize tool output with Gemini
        synthesis_prompt = (
            f"User Prompt: {prompt}\n\n"
            f"Tool '{self.tool_name}' Output:\n{raw_tool_result}\n\n"
            "Please provide a clear, helpful, and comprehensive response answering the user query based on the tool results."
        )

        response = await self.llm_client.generate(
            prompt=synthesis_prompt,
            system_prompt="You are an expert AI assistant providing insights and summarizing tool results accurately.",
            temperature=0.7,
        )

        return AgentResult(
            content=response.content,
            agent_id=self.agent_id,
            agent_name=self.name,
            metadata={
                "tool_name": self.tool_name,
                "arguments": arguments,
                "raw_result": raw_tool_result,
                "provider": self.llm_client.provider_name,
                "model": response.model,
                "usage": response.usage,
            },
        )

    async def stream(
        self, prompt: str, *, context: dict[str, Any] | None = None
    ) -> AsyncGenerator[str, None]:
        """Stream synthesized answer from tool execution."""
        arguments = await self._extract_tool_arguments(prompt)

        try:
            raw_tool_result = await self.mcp_client.call_tool(self.tool_name, arguments)
        except Exception as e:
            yield f"Error executing tool '{self.tool_name}': {e!s}"
            return

        synthesis_prompt = (
            f"User Prompt: {prompt}\n\n"
            f"Tool '{self.tool_name}' Output:\n{raw_tool_result}\n\n"
            "Please provide a clear, helpful, and comprehensive response answering the user query based on the tool results."
        )

        async for token in self.llm_client.stream(
            prompt=synthesis_prompt,
            system_prompt="You are an expert AI assistant summarizing tool results.",
            temperature=0.7,
        ):
            yield token
