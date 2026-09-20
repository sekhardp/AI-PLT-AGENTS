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


def parse_model_selection(
    model_raw: str | None,
    local_client: Any | None,
    gemini_client: Any | None,
) -> tuple[str | None, str | None, str | None]:
    """Parse user model preference into (routed_to, model_name, routing_strategy).

    Returns (None, None, None) if 'auto' or unspecified.
    """
    if not model_raw or model_raw.strip().lower() in ("auto", "none", ""):
        return None, None, None

    raw = model_raw.strip()
    low = raw.lower().replace("_", "-").replace(" ", "-")

    # Local model aliases
    local_default_name = getattr(local_client, "model_name", "Qwen/Qwen2.5-7B-Instruct")
    if (
        "qwen" in low
        or "local" in low
        or low in ("vllm", "ollama")
        or raw == local_default_name
    ):
        return "local", local_default_name, "LOCAL_ONLY"

    # Frontier model aliases
    frontier_default_name = getattr(gemini_client, "model_name", "gemini-2.5-flash")
    if "gemini" in low or "frontier" in low or "vertex" in low or raw == frontier_default_name:
        if "pro" in low:
            model_name = "gemini-1.5-pro" if "1.5" in low else "gemini-2.5-pro"
        else:
            model_name = "gemini-2.5-flash"
        return "frontier", model_name, "FRONTIER_ONLY"

    # Direct custom model string
    return None, raw, None


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
    forced_routed_to, forced_model_name, forced_strategy = parse_model_selection(
        req.model, local_client, gemini_client
    )

    if forced_strategy:
        routed_to = forced_routed_to
        model_name = forced_model_name
        context["routing_strategy"] = forced_strategy
        context["routed_to"] = routed_to
        context["model"] = model_name
    elif req.routing_strategy:
        strat = req.routing_strategy.upper()
        context["routing_strategy"] = strat
        if strat == "LOCAL_ONLY":
            routed_to = "local"
            model_name = getattr(local_client, "model_name", "Qwen/Qwen2.5-7B-Instruct")
            context["routed_to"] = "local"
            context["model"] = model_name
        elif strat == "FRONTIER_ONLY":
            routed_to = "frontier"
            model_name = getattr(gemini_client, "model_name", "gemini-2.5-flash")
            context["routed_to"] = "frontier"
            context["model"] = model_name
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
        context["routed_to"] = routed_to
        context["model"] = model_name

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
                        event_type = item.get("type")
                        if event_type == "routing_fallback":
                            fb_routed_to = item.get("routed_to", "frontier")
                            fb_model = item.get("model", "gemini-2.5-flash")
                            current_routed_to = fb_routed_to
                            current_model = fb_model
                            fallback_event = {
                                "type": "routing_decision",
                                "stage": "fallback",
                                "routed_to": fb_routed_to,
                                "model": fb_model,
                                "agent_id": agent.agent_id,
                                "fallback_triggered": True,
                                "reason": item.get("reason", "Local LLM unreachable, fell back to Frontier"),
                            }
                            yield f"data: {json.dumps(fallback_event)}\n\n"
                            await asyncio.sleep(0)
                            continue

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
    except ConnectionError as ce:
        logger.error("execute_agent_connection_error", error=str(ce))
        raise HTTPException(status_code=503, detail=str(ce)) from ce
    finally:
        if sid and _active_executions.get(sid) is current_task:
            _active_executions.pop(sid, None)
