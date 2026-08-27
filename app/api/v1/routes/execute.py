import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.agents.registry import AgentRegistry
from app.api.v1.schemas.execute import ExecuteRequest, ExecuteResponse

router = APIRouter()


def get_registry(request: Request) -> AgentRegistry:
    return request.app.state.registry


@router.post("", response_model=ExecuteResponse, tags=["Execution"])
async def execute_agent(req: ExecuteRequest, request: Request):
    registry = get_registry(request)

    if req.agent_id:
        agent = registry.get(req.agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{req.agent_id}' not found")
    else:
        agent = getattr(request.app.state, "orchestrator", None)
        if not agent:
            raise HTTPException(status_code=503, detail="Orchestrator is not initialized")

    context = dict(req.context or {})
    if req.routing_strategy:
        context["routing_strategy"] = req.routing_strategy
    if req.chat_history:
        context["chat_history"] = req.chat_history

    ai_router = getattr(request.app.state, "router", None)
    local_client = getattr(request.app.state, "local_client", None)
    gemini_client = getattr(request.app.state, "gemini_client", None)

    routed_to = None
    model_name = None
    complexity_score = None

    if ai_router:
        decision = ai_router.classify(
            req.prompt, strategy_override=req.routing_strategy, context=context
        )
        routed_to = decision.target
        complexity_score = decision.complexity_score
        model_name = (
            getattr(local_client, "model_name", "Qwen/Qwen2.5-7B-Instruct")
            if decision.target == "local"
            else getattr(gemini_client, "model_name", "gemini-2.5-flash")
        )

    if req.stream:
        async def event_generator():
            # 1. Immediately inform client that AI Router is actively evaluating the query
            init_eval_data = json.dumps({
                "type": "routing_init",
                "stage": "ai_router",
                "routed_to": "ai_router",
                "model": "AI Router",
                "agent_id": agent.agent_id,
            })
            yield f"data: {init_eval_data}\n\n"

            sent_decision_event = False
            async for token in agent.stream(req.prompt, context=context):
                current_routed_to = context.get("routed_to", routed_to or "local")
                current_model = context.get("model", model_name or "Qwen/Qwen2.5-7B-Instruct")

                # 2. As soon as routing decision is resolved and first token arrives, update tag
                if not sent_decision_event:
                    sent_decision_event = True
                    decision_data = json.dumps({
                        "type": "routing_decision",
                        "stage": "executing",
                        "routed_to": current_routed_to,
                        "model": current_model,
                        "agent_id": agent.agent_id,
                        "fallback_triggered": context.get("fallback_triggered", False),
                    })
                    yield f"data: {decision_data}\n\n"

                data = json.dumps({
                    "token": token,
                    "agent_id": agent.agent_id,
                    "routed_to": current_routed_to,
                    "model": current_model,
                })
                yield f"data: {data}\n\n"
                await asyncio.sleep(0)

            final_routed_to = context.get("routed_to", routed_to or "frontier")
            final_model = context.get("model", model_name or "gemini-2.5-flash")
            yield f"data: {json.dumps({'done': True, 'agent_id': agent.agent_id, 'routed_to': final_routed_to, 'model': final_model})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    result = await agent.execute(req.prompt, context=context)
    return ExecuteResponse(
        content=result.content,
        agent_id=result.agent_id,
        agent_name=result.agent_name,
        trace_id=result.trace_id,
        routed_to=result.metadata.get("routed_to", routed_to),
        model=result.metadata.get("model", model_name),
        metadata=result.metadata,
    )
