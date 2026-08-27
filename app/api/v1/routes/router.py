from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.clients.local_llm_client import LocalLLMClient
from app.router.smart_router import RoutingStrategy, SmartAIRouter

router = APIRouter()


class ClassifyRequest(BaseModel):
    prompt: str = Field(..., description="Prompt to evaluate for routing")
    routing_strategy: str | None = Field(None, description="Optional strategy override")


class ClassifyResponse(BaseModel):
    target: str = Field(..., description="Predicted routing target: 'local' or 'frontier'")
    strategy: str = Field(..., description="Routing strategy applied")
    complexity_score: float = Field(..., description="Calculated complexity score (0.0 - 1.0)")
    reason: str = Field(..., description="Rationale for the routing decision")
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateStrategyRequest(BaseModel):
    strategy: str = Field(..., description="New default routing strategy (AUTO, LOCAL_FIRST, FRONTIER_FIRST, LOCAL_ONLY, FRONTIER_ONLY)")
    complexity_threshold: float | None = Field(None, ge=0.0, le=1.0, description="Optional updated threshold")


@router.get("/status", tags=["Router"])
async def get_router_status(request: Request):
    """Retrieve operational state, circuit breaker status, and model health for both Local and Frontier."""
    ai_router: SmartAIRouter | None = getattr(request.app.state, "router", None)
    local_client: LocalLLMClient | None = getattr(request.app.state, "local_client", None)
    gemini_client = getattr(request.app.state, "gemini_client", None)

    if not ai_router:
        raise HTTPException(status_code=503, detail="Router is not initialized")

    local_health = {}
    if local_client:
        if hasattr(local_client, "check_liveness"):
            local_health = await local_client.check_liveness()
        else:
            local_health = local_client.health()

    frontier_health = gemini_client.health() if gemini_client else {}

    return {
        "status": "ok",
        "router": ai_router.status(),
        "local_llm": local_health,
        "frontier_llm": frontier_health,
    }


@router.post("/classify", response_model=ClassifyResponse, tags=["Router"])
async def classify_prompt(req: ClassifyRequest, request: Request) -> ClassifyResponse:
    """Preview how the Smart Router will navigate a given prompt without executing the LLM."""
    ai_router: SmartAIRouter | None = getattr(request.app.state, "router", None)
    if not ai_router:
        raise HTTPException(status_code=503, detail="Router is not initialized")

    decision = ai_router.classify(req.prompt, strategy_override=req.routing_strategy)
    return ClassifyResponse(
        target=decision.target,
        strategy=decision.strategy.value,
        complexity_score=decision.complexity_score,
        reason=decision.reason,
        metadata=decision.metadata,
    )


@router.post("/strategy", tags=["Router"])
async def update_strategy(req: UpdateStrategyRequest, request: Request):
    """Dynamically update routing strategy or complexity threshold at runtime."""
    ai_router: SmartAIRouter | None = getattr(request.app.state, "router", None)
    if not ai_router:
        raise HTTPException(status_code=503, detail="Router is not initialized")

    try:
        new_strategy = RoutingStrategy(req.strategy.upper())
    except ValueError:
        valid_options = [s.value for s in RoutingStrategy]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy '{req.strategy}'. Valid options: {valid_options}",
        )

    ai_router.default_strategy = new_strategy
    if req.complexity_threshold is not None:
        ai_router.complexity_threshold = req.complexity_threshold
        ai_router.scorer.threshold = req.complexity_threshold

    return {
        "status": "ok",
        "updated_strategy": ai_router.default_strategy.value,
        "updated_threshold": ai_router.complexity_threshold,
    }
