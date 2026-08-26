from typing import Any
from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    prompt: str = Field(..., description="User prompt to execute")
    agent_id: str | None = Field(None, description="Optional specific agent ID to invoke")
    stream: bool = Field(False, description="Whether to stream response tokens via SSE")
    context: dict[str, Any] | None = Field(None, description="Optional context metadata")


class ExecuteResponse(BaseModel):
    content: str = Field(..., description="Generated text content")
    agent_id: str = Field(..., description="ID of the executing agent")
    agent_name: str = Field(..., description="Name of the executing agent")
    trace_id: str = Field(..., description="Unique execution trace ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Execution metadata and usage metrics")


class StreamChunk(BaseModel):
    token: str | None = None
    done: bool = False
    agent_id: str | None = None
