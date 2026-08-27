from fastapi import APIRouter, Request

from app.agents.registry import AgentRegistry
from app.api.v1.schemas.health import HealthResponse

router = APIRouter()


def get_registry(request: Request) -> AgentRegistry:
    return getattr(request.app.state, "registry", None)


@router.get("", response_model=HealthResponse, tags=["Health"])
async def get_health(request: Request) -> HealthResponse:
    registry = get_registry(request)
    mcp_client = getattr(request.app.state, "mcp_client", None)
    ai_router = getattr(request.app.state, "router", None)
    gemini_client = getattr(request.app.state, "gemini_client", None)
    local_client = getattr(request.app.state, "local_client", None)

    mcp_info = {
        "registry_url": getattr(mcp_client, "registry_url", None),
        "last_error": getattr(mcp_client, "last_error", None),
        "status": "connected" if registry and registry.count > 1 else "no_tools_registered",
    } if mcp_client else {}

    router_info = ai_router.status() if ai_router else {}
    models_info = {
        "frontier": gemini_client.health() if gemini_client else {},
        "local": local_client.health() if local_client else {},
    }

    return HealthResponse(
        status="ok",
        service="ai-plt-agents",
        agents=registry.health() if registry else {},
        mcp_gateway=mcp_info,
        router=router_info,
        models=models_info,
    )
