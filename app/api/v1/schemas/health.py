from typing import Any
from pydantic import BaseModel, Field


class AgentHealthStatus(BaseModel):
    agent_id: str
    name: str
    status: str


class HealthResponse(BaseModel):
    status: str = Field("ok", description="Service health status")
    service: str = Field("ai-plt-agents", description="Service name")
    agents: dict[str, Any] = Field(default_factory=dict, description="Aggregate health of all agents")
    mcp_gateway: dict[str, Any] = Field(default_factory=dict, description="MCP Registry Gateway connection info")
