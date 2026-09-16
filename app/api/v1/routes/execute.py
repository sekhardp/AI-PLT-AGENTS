import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.agents.registry import AgentRegistry
from app.api.v1.schemas.execute import ExecuteRequest, ExecuteResponse, StopExecuteRequest

logger = logging.getLogger(__name__)

router = APIRouter()

# Active in-flight async execution tasks keyed by session_id
_active_executions: dict[str, asyncio.Task] = {}


def get_registry(request: Request) -> AgentRegistry:
    return request.app.state.registry


@router.post("/stop", tags=["Execution"])
async def stop_execution(req: StopExecuteRequest, request: Request):
    """Cancel a running agent execution task immediately."""
    sid = req.session_id.strip() if req.session_id else ""
    if not sid:
        raise HTTPException(status_code=400, detail="session_id is required")

    task = _active_executions.get(sid)
    if task and not task.done():
        logger.info("Cancelling active agent task for session=%s", sid)
        task.cancel()
        return {"status": "stopped", "session_id": sid, "message": "Agent execution cancelled"}

    return {"status": "idle", "session_id": sid, "message": "No running agent execution found for session"}


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

    context: dict[str, Any] = dict(req.context or {})
    if req.session_id:
        context["session_id"] = req.session_id
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

    # Handle model preference override
    if req.model and req.model.strip().lower() != "auto":
        clean_model = req.model.strip()
        clean_model_lower = clean_model.lower()
        if clean_model_lower in ("qwen/qwen2.5-7b-instruct", "qwen-2.5-7b", "local", "qwen"):
            routed_to = "local"
            model_name = getattr(local_client, "model_name", "Qwen/Qwen2.5-7B-Instruct")
            context["routing_strategy"] = "LOCAL_ONLY"
            context["routed_to"] = "local"
            context["model"] = model_name
        elif clean_model_lower in ("gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-pro", "frontier"):
            routed_to = "frontier"
            model_name = clean_model if clean_model_lower != "frontier" else getattr(gemini_client, "model_name", "gemini-2.5-flash")
            context["routing_strategy"] = "FRONTIER_ONLY"
            context["routed_to"] = "frontier"
            context["model"] = model_name
        else:
            context["model"] = clean_model
            model_name = clean_model
    elif ai_router:
        decision = ai_router.classify(
            req.prompt, strategy_override=req.routing_strategy, context=context
        )
        routed_to = decision.target
        complexity_score = decision.complexity_score
        context["complexity_score"] = complexity_score
        model_name = (
            getattr(local_client, "model_name", "Qwen/Qwen2.5-7B-Instruct")
            if decision.target == "local"
            else getattr(gemini_client, "model_name", "gemini-2.5-flash")
        )

    if req.stream:
        sid = req.session_id or ""

        async def event_generator():
            current_task = asyncio.current_task()
            if sid and current_task:
                _active_executions[sid] = current_task

            try:
                # 1. Immediately inform client that AI Router is actively evaluating the query
                init_eval_data = json.dumps({
                    "type": "routing_init",
                    "stage": "ai_router",
                    "routed_to": routed_to or "ai_router",
                    "model": model_name or "AI Router",
                    "agent_id": agent.agent_id,
                })
                yield f"data: {init_eval_data}\n\n"

                sent_decision_event = False
                async for item in agent.stream(req.prompt, context=context):
                    current_routed_to = context.get("routed_to", routed_to or "local")
                    current_model = context.get("model", model_name or "Qwen/Qwen2.5-7B-Instruct")

                    if isinstance(item, dict):
                        tool_event = dict(item)
                        tool_event["agent_id"] = agent.agent_id
                        tool_event["routed_to"] = current_routed_to
                        tool_event["model"] = current_model
                        yield f"data: {json.dumps(tool_event)}\n\n"
                        await asyncio.sleep(0)
                        continue

                    token = str(item)
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

                usage = context.get("usage") or {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }
                total_tokens = usage.get("total_tokens", 0)
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)

                done_payload = {
                    "done": True,
                    "agent_id": agent.agent_id,
                    "routed_to": final_routed_to,
                    "model": final_model,
                    "usage": usage,
                    "total_tokens": total_tokens,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }
                yield f"data: {json.dumps(done_payload)}\n\n"
            except asyncio.CancelledError:
                logger.info("Streaming agent execution cancelled by client/user (session=%s)", sid)
                yield f"data: {json.dumps({'done': True, 'stopped': True, 'session_id': sid, 'token': ''})}\n\n"
            finally:
                if sid and _active_executions.get(sid) is current_task:
                    _active_executions.pop(sid, None)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Non-streaming execution
    sid = req.session_id or ""
    current_task = asyncio.current_task()
    if sid and current_task:
        _active_executions[sid] = current_task

    try:
        result = await agent.execute(req.prompt, context=context)
        usage = result.metadata.get("usage") or context.get("usage") or {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        total_tokens = usage.get("total_tokens", 0)
        result.metadata["total_tokens"] = total_tokens
        result.metadata["usage"] = usage

        return ExecuteResponse(
            content=result.content,
            agent_id=result.agent_id,
            agent_name=result.agent_name,
            trace_id=result.trace_id,
            routed_to=result.metadata.get("routed_to", routed_to),
            model=result.metadata.get("model", model_name),
            usage=usage,
            total_tokens=total_tokens,
            metadata=result.metadata,
        )
    finally:
        if sid and _active_executions.get(sid) is current_task:
            _active_executions.pop(sid, None)
