from fastapi import APIRouter, Request
from app.api.v1.schemas.health import HealthResponse
from app.agents.registry import AgentRegistry

router = APIRouter()


def get_registry(request: Request) -> AgentRegistry:
    return getattr(request.app.state, "registry", None)


@router.get("", response_model=HealthResponse, tags=["Health"])
async def get_health(request: Request) -> HealthResponse:
    registry = get_registry(request)
    return HealthResponse(
        status="ok",
        service="ai-plt-agents",
        agents=registry.health() if registry else {},
    )
