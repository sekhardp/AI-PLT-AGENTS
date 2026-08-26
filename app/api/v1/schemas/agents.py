from pydantic import BaseModel, Field


class AgentInfo(BaseModel):
    agent_id: str
    name: str
    description: str
    capabilities: list[str]
    status: str = "active"


class AgentListResponse(BaseModel):
    agents: list[AgentInfo]
    total: int
