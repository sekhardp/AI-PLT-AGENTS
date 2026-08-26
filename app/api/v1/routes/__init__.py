from fastapi import APIRouter
from .health import router as health_router
from .agents import router as agents_router
from .execute import router as execute_router

v1_router = APIRouter()
v1_router.include_router(health_router, prefix="/health", tags=["Health"])
v1_router.include_router(agents_router, prefix="/agents", tags=["Agents"])
v1_router.include_router(execute_router, prefix="/execute", tags=["Execution"])

__all__ = ["v1_router"]
