from fastapi import APIRouter, HTTPException, Request
from app.api.v1.schemas.agents import AgentInfo, AgentListResponse
from app.agents.registry import AgentRegistry

router = APIRouter()


def get_registry(request: Request) -> AgentRegistry:
    return request.app.state.registry


@router.get("", response_model=AgentListResponse, tags=["Agents"])
async def list_agents(request: Request) -> AgentListResponse:
    registry = get_registry(request)
    agents = [AgentInfo(**a.info()) for a in registry.list_agents()]
    return AgentListResponse(agents=agents, total=len(agents))


@router.get("/{agent_id}", response_model=AgentInfo, tags=["Agents"])
async def get_agent(agent_id: str, request: Request) -> AgentInfo:
    registry = get_registry(request)
    agent = registry.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return AgentInfo(**agent.info())


@router.get("/{agent_id}/health", tags=["Agents"])
async def agent_health(agent_id: str, request: Request):
    registry = get_registry(request)
    agent = registry.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent.health()
