from __future__ import annotations

import pytest
from app.agents.deps import AgentDeps
from app.agents.mcp_tools import build_mcp_tools_from_definitions, create_mcp_tool
from app.agents.orchestrator import OrchestratorAgent
from app.agents.registry import AgentRegistry
from app.core.settings import app_settings
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel
from tests.conftest import MockLLMClient, MockMCPRegistryClient


@pytest.mark.asyncio
async def test_dynamic_mcp_tool_creation_and_execution():
    mcp_client = MockMCPRegistryClient()
    tool = create_mcp_tool(
        tool_name="get_weather",
        description="Get real-time weather",
        tool_schema={"type": "object", "properties": {"latitude": {"type": "number"}, "longitude": {"type": "number"}}},
    )

    assert tool.name == "get_weather"

    # Multi-hop execution: turn 1 calls tool, turn 2 summarizes
    async def mock_fn(messages, info):
        has_return = any(isinstance(p, ToolReturnPart) for m in messages for p in getattr(m, "parts", []))
        if not has_return:
            return ModelResponse(parts=[ToolCallPart("get_weather", {"latitude": 37.7, "longitude": -122.4})])
        return ModelResponse(parts=[TextPart("The temperature in SF is 22.5 C and sunny.")])

    agent = Agent[AgentDeps, str](
        model=FunctionModel(mock_fn),
        deps_type=AgentDeps,
        tools=[tool],
    )

    deps = AgentDeps(mcp_client=mcp_client)
    res = await agent.run("What is the weather?", deps=deps)

    assert "22.5 C" in res.output
    assert res.usage.total_tokens > 0


@pytest.mark.asyncio
async def test_build_mcp_tools_from_definitions():
    definitions = [
        {"name": "tool_a", "description": "Tool A description", "input_schema": {}},
        {"name": "tool_b", "description": "Tool B description", "input_schema": {}},
    ]
    tools = build_mcp_tools_from_definitions(definitions)
    assert len(tools) == 2
    assert tools[0].name == "tool_a"
    assert tools[1].name == "tool_b"


@pytest.mark.asyncio
async def test_pydantic_ai_orchestrator_system_prompt_injection(registry: AgentRegistry, mock_llm: MockLLMClient):
    orchestrator = OrchestratorAgent(registry=registry, llm_client=mock_llm)
    registry.register(orchestrator)

    context = {
        "user_id": "usr_999",
        "document_ids": ["doc_alpha", "doc_beta"],
    }
    result = await orchestrator.execute("Hello AI platform", context=context)
    assert result.agent_id == "orchestrator-01"
    assert len(result.content) > 0


def test_logfire_settings():
    lf = app_settings.logfire_settings
    assert lf.PROJECT_NAME == "ai-plt-agents"
    assert lf.SERVICE_NAME == "ai-plt-agents"


@pytest.mark.asyncio
async def test_fallback_model_integration():
    from app.clients.local_llm_client import LocalLLMClient
    from app.clients.router_client import SmartRouterClient
    from app.router.smart_router import RoutingStrategy, SmartAIRouter
    from pydantic_ai.models.fallback import FallbackModel
    from pydantic_ai.models.test import TestModel

    local_client = LocalLLMClient(base_url="http://mock-local:8000/v1")
    frontier_client = LocalLLMClient(base_url="http://mock-frontier:8000/v1")
    local_client._model = TestModel(custom_output_text="Local text")
    frontier_client._model = TestModel(custom_output_text="Frontier text")

    router = SmartAIRouter(default_strategy=RoutingStrategy.AUTO, fallback_enabled=True)
    router_client = SmartRouterClient(frontier_client=frontier_client, local_client=local_client, router=router)

    fallback_model = router_client.get_pydantic_model(target="local")
    assert isinstance(fallback_model, FallbackModel)

    agent = Agent(model=fallback_model)
    res = await agent.run("Test query")
    assert res.output == "Local text"
    await local_client.aclose()
    await frontier_client.aclose()

