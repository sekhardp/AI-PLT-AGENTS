from fastapi import APIRouter

from .agents import router as agents_router
from .execute import router as execute_router
from .health import router as health_router
from .router import router as router_router

v1_router = APIRouter()
v1_router.include_router(health_router, prefix="/health", tags=["Health"])
v1_router.include_router(agents_router, prefix="/agents", tags=["Agents"])
v1_router.include_router(execute_router, prefix="/execute", tags=["Execution"])
v1_router.include_router(router_router, prefix="/router", tags=["Router"])

__all__ = ["v1_router"]
