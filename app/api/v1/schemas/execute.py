from typing import Any

from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    prompt: str = Field(..., description="User prompt to execute")
    agent_id: str | None = Field(None, description="Optional specific agent ID to invoke")
    routing_strategy: str | None = Field(
        None,
        description="Optional routing strategy override: AUTO, LOCAL_FIRST, FRONTIER_FIRST, LOCAL_ONLY, FRONTIER_ONLY",
    )
    stream: bool = Field(False, description="Whether to stream response tokens via SSE")
    context: dict[str, Any] | None = Field(None, description="Optional context metadata")
    chat_history: list[dict[str, str]] | None = Field(
        None,
        description="Prior conversation turns formatted as [{'role': 'user'|'assistant', 'content': '...'}]",
    )


class ExecuteResponse(BaseModel):
    content: str = Field(..., description="Generated text content")
    agent_id: str = Field(..., description="ID of the executing agent")
    agent_name: str = Field(..., description="Name of the executing agent")
    trace_id: str = Field(..., description="Unique execution trace ID")
    routed_to: str | None = Field(
        None, description="Model tier executing the request ('local' or 'frontier')"
    )
    model: str | None = Field(
        None, description="Specific model name (e.g. 'Qwen/Qwen2.5-7B-Instruct' or 'gemini-2.5-flash')"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Execution metadata and usage metrics"
    )


class StreamChunk(BaseModel):
    token: str | None = None
    done: bool = False
    agent_id: str | None = None
    routed_to: str | None = None
    model: str | None = None
    complexity_score: float | None = None
    type: str | None = None
