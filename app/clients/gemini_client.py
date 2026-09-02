from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from google import genai
from google.genai import types

from app.clients.base import BaseLLMClient, LLMResponse, ToolCall

logger = structlog.get_logger(__name__)


def _extract_gemini_usage(um: Any) -> dict[str, int]:
    if not um:
        return {}
    if isinstance(um, dict):
        prompt = um.get("prompt_token_count") or um.get("prompt_tokens") or 0
        completion = um.get("candidates_token_count") or um.get("completion_tokens") or 0
        total = um.get("total_token_count") or um.get("total_tokens") or (prompt + completion)
    else:
        prompt = (
            getattr(um, "prompt_token_count", None)
            or getattr(um, "prompt_tokens", None)
            or 0
        )
        completion = (
            getattr(um, "candidates_token_count", None)
            or getattr(um, "completion_tokens", None)
            or getattr(um, "candidates_tokens", None)
            or 0
        )
        total = (
            getattr(um, "total_token_count", None)
            or getattr(um, "total_tokens", None)
            or (prompt + completion)
        )
    return {
        "prompt_tokens": int(prompt),
        "completion_tokens": int(completion),
        "total_tokens": int(total),
    }


class GeminiClient(BaseLLMClient):
    """Production LLM client for Google Gemini models via Vertex AI using the Google GenAI SDK."""

    provider_name = "gemini"

    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        model_name: str = "gemini-2.5-flash",
        default_temperature: float = 0.7,
        default_max_tokens: int = 4096,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens

        self._client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
        )

        logger.info(
            "gemini_client_initialized",
            project_id=project_id,
            location=location,
            model_name=model_name,
        )

    def _build_tools(self, tools: list[dict[str, Any]] | None) -> list[types.Tool] | None:
        """Convert MCP JSON schemas to Gemini Tool declarations."""
        if not tools:
            return None
        declarations = []
        for t in tools:
            schema = t.get("input_schema") or t.get("parameters") or {}
            declarations.append(
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=schema if schema else None,
                )
            )
        return [types.Tool(function_declarations=declarations)]

    def _build_contents(
        self,
        prompt: str | None = None,
        chat_history: list[dict[str, Any]] | None = None,
    ) -> list[types.Content] | str:
        if not chat_history:
            return prompt or ""

        contents: list[types.Content] = []
        for m in chat_history:
            role = "user" if m.get("role") in ("user", "human") else "model"
            parts: list[types.Part] = []

            # 1. Model emitted tool calls
            if m.get("tool_calls"):
                for tc in m["tool_calls"]:
                    name = tc.name if hasattr(tc, "name") else tc.get("name")
                    args = tc.arguments if hasattr(tc, "arguments") else tc.get("arguments", {})
                    parts.append(types.Part.from_function_call(name=name, args=args))
                role = "model"
            # 2. Tool response back to model
            elif m.get("role") == "tool" or m.get("type") == "tool_response":
                tool_name = m.get("name") or "tool"
                res = m.get("content") or m.get("response") or {}
                if isinstance(res, str):
                    res = {"output": res}
                parts.append(types.Part.from_function_response(name=tool_name, response=res))
                role = "user"
            # 3. Standard text content
            elif m.get("content"):
                parts.append(types.Part.from_text(text=m["content"]))

            if parts:
                contents.append(types.Content(role=role, parts=parts))

        if prompt:
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                )
            )
        return contents

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        chat_history: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate full completion or function calls using Gemini on Vertex AI."""
        temp = temperature if temperature is not None else self.default_temperature
        max_tok = max_tokens if max_tokens is not None else self.default_max_tokens

        config = types.GenerateContentConfig(
            temperature=temp,
            max_output_tokens=max_tok,
            system_instruction=system_prompt if system_prompt else None,
            tools=self._build_tools(tools),
        )

        start = time.perf_counter()
        response = await self._client.aio.models.generate_content(
            model=self.model_name,
            contents=self._build_contents(prompt, chat_history),
            config=config,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        usage: dict[str, int] = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = _extract_gemini_usage(response.usage_metadata)

        content = response.text or ""

        # Extract native function calls if emitted by Gemini
        tool_calls: list[ToolCall] = []
        if hasattr(response, "function_calls") and response.function_calls:
            for fc in response.function_calls:
                args = dict(fc.args) if hasattr(fc, "args") and fc.args else {}
                tool_calls.append(
                    ToolCall(
                        id=getattr(fc, "id", fc.name) or fc.name,
                        name=fc.name,
                        arguments=args,
                    )
                )

        logger.info(
            "gemini_generate_completed",
            model=self.model_name,
            latency_ms=round(latency_ms, 1),
            total_tokens=usage.get("total_tokens", 0),
            tool_calls_count=len(tool_calls),
        )

        return LLMResponse(
            content=content,
            model=self.model_name,
            provider=self.provider_name,
            usage=usage,
            latency_ms=latency_ms,
            tool_calls=tool_calls,
        )

    async def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        chat_history: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens asynchronously from Gemini on Vertex AI and capture exact model usage."""
        temp = temperature if temperature is not None else self.default_temperature
        max_tok = max_tokens if max_tokens is not None else self.default_max_tokens

        config = types.GenerateContentConfig(
            temperature=temp,
            max_output_tokens=max_tok,
            system_instruction=system_prompt if system_prompt else None,
            tools=self._build_tools(tools),
        )

        stream_response = await self._client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=self._build_contents(prompt, chat_history),
            config=config,
        )

        async for chunk in stream_response:
            if hasattr(chunk, "usage_metadata") and chunk.usage_metadata and context is not None:
                context["usage"] = _extract_gemini_usage(chunk.usage_metadata)
            if chunk.text:
                yield chunk.text

    def health(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "project_id": self.project_id,
            "location": self.location,
            "status": "healthy",
        }
