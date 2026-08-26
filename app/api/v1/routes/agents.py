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


@router.post("/sync", tags=["Agents"])
async def sync_agents(request: Request):
    """Dynamically re-sync tools from the MCP Registry Gateway without restarting."""
    registry = get_registry(request)
    mcp_client = getattr(request.app.state, "mcp_client", None)
    gemini_client = getattr(request.app.state, "gemini_client", None)
    if not mcp_client or not gemini_client or not registry:
        raise HTTPException(status_code=503, detail="Services not fully initialized")

    from app.core.bootstrap import sync_mcp_tools
    try:
        tools = await sync_mcp_tools(mcp_client, registry, gemini_client)
        return {
            "status": "ok",
            "discovered_tools_count": len(tools),
            "total_registered_agents": registry.count,
            "tools": [t["name"] for t in tools],
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"MCP sync failed: {e!s}")
