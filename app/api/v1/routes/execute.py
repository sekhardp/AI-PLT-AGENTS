import json
import asyncio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.api.v1.schemas.execute import ExecuteRequest, ExecuteResponse
from app.agents.registry import AgentRegistry

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

    if req.stream:
        async def event_generator():
            async for token in agent.stream(req.prompt, context=req.context):
                data = json.dumps({"token": token, "agent_id": agent.agent_id})
                yield f"data: {data}\n\n"
                await asyncio.sleep(0)
            yield f"data: {json.dumps({'done': True, 'agent_id': agent.agent_id})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    result = await agent.execute(req.prompt, context=req.context)
    return ExecuteResponse(
        content=result.content,
        agent_id=result.agent_id,
        agent_name=result.agent_name,
        trace_id=result.trace_id,
        metadata=result.metadata,
    )
