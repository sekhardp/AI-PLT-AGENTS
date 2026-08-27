from fastapi import APIRouter

from app.api.v1.routes import v1_router
from app.api.v1.routes.agents import router as agents_router
from app.api.v1.routes.execute import router as execute_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.router import router as router_router

root_router = APIRouter()

# Main V1 API route prefix
root_router.include_router(v1_router, prefix="/api/v1")

# Backward-compatible root endpoint aliases
root_router.include_router(health_router, prefix="/health", tags=["Root Aliases"], include_in_schema=False)
root_router.include_router(agents_router, prefix="/agents", tags=["Root Aliases"], include_in_schema=False)
root_router.include_router(execute_router, prefix="/execute", tags=["Root Aliases"], include_in_schema=False)
root_router.include_router(router_router, prefix="/router", tags=["Root Aliases"], include_in_schema=False)
