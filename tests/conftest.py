from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from app.agents.mcp import MCPAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.registry import AgentRegistry
from app.clients.base import BaseLLMClient, LLMResponse
from app.clients.mcp_client import MCPRegistryClient
from app.core.bootstrap import create_app
from httpx import ASGITransport, AsyncClient


class MockLLMClient(BaseLLMClient):
    """Deterministic mock LLM client for fast, reliable unit testing."""

    provider_name = "mock-gemini"
    model_name = "mock-model"

    def __init__(self, fixed_response: str = "Mocked LLM Answer") -> None:
        self.fixed_response = fixed_response

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        # Check if the prompt was for tool argument extraction
        if system_prompt and "parameter extractor" in system_prompt.lower():
            content = json.dumps({"query": "SELECT * FROM dataset", "limit": 10})
        elif system_prompt and "routing dispatcher" in system_prompt.lower():
            if "weather" in prompt.lower():
                content = json.dumps({"selected_agent_id": "mcp-get_weather", "reason": "weather_query"})
            else:
                content = json.dumps({"selected_agent_id": None, "reason": "general_query"})
        elif system_prompt and "intelligent ai router" in system_prompt.lower():
            if self.fixed_response.strip().startswith("{"):
                content = self.fixed_response
            elif any(w in prompt.lower() for w in ("complex", "consensus", "proof", "architect", "distributed", "race")):
                content = json.dumps({"target": "frontier", "reason": "complex reasoning required"})
            else:
                content = json.dumps({"target": "local", "reason": "simple query"})
        elif self.fixed_response.strip().startswith("{"):
            content = self.fixed_response
        else:
            content = f"{self.fixed_response} to: {prompt[:40]}"

        return LLMResponse(
            content=content,
            model="mock-gemini-2.5-flash",
            provider=self.provider_name,
            usage={"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
            latency_ms=12.5,
        )

    async def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        tokens = ["This ", "is ", "a ", "streamed ", "mock ", "response."]
        for token in tokens:
            yield token

    def health(self) -> dict[str, Any]:
        return {"provider": self.provider_name, "status": "healthy"}

    async def check_liveness(self) -> dict[str, Any]:
        return {"provider": self.provider_name, "status": "healthy", "latency_ms": 1.0}


class MockMCPRegistryClient(MCPRegistryClient):
    """Mock MCP Client for offline testing."""

    def __init__(self) -> None:
        super().__init__(registry_url="http://mock-mcp-registry:8081/sse", timeout_seconds=5)

    async def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "get_weather",
                "description": "Get real-time weather information for coordinates",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"},
                    },
                    "required": ["latitude", "longitude"],
                },
            }
        ]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        if tool_name == "get_weather":
            return json.dumps({"temperature": 22.5, "unit": "celsius", "condition": "Sunny"})
        return json.dumps({"result": "Mock tool output"})


@pytest.fixture
def mock_llm() -> MockLLMClient:
    return MockLLMClient()


@pytest.fixture
def mock_mcp_client() -> MockMCPRegistryClient:
    return MockMCPRegistryClient()


@pytest.fixture
def registry() -> AgentRegistry:
    return AgentRegistry()


@pytest.fixture
def orchestrator(registry: AgentRegistry, mock_llm: MockLLMClient) -> OrchestratorAgent:
    orch = OrchestratorAgent(registry=registry, llm_client=mock_llm)
    registry.register(orch)
    return orch


@pytest.fixture
def mcp_agent(mock_mcp_client: MockMCPRegistryClient, mock_llm: MockLLMClient) -> MCPAgent:
    return MCPAgent(
        agent_id="mcp-get_weather",
        name="MCP Agent - get_weather",
        description="Get real-time weather for coordinates",
        tool_name="get_weather",
        tool_schema={"type": "object", "properties": {"latitude": {"type": "number"}}},
        mcp_client=mock_mcp_client,
        llm_client=mock_llm,
    )


@pytest.fixture
async def test_app(mock_llm: MockLLMClient, mock_mcp_client: MockMCPRegistryClient):
    from app.clients.router_client import SmartRouterClient
    from app.router.smart_router import RoutingStrategy, SmartAIRouter

    app = create_app()
    registry = AgentRegistry()

    router = SmartAIRouter(default_strategy=RoutingStrategy.AUTO, complexity_threshold=0.55)
    local_client = MockLLMClient(fixed_response="Mocked Local Answer")
    local_client.provider_name = "mock-local"
    router_client = SmartRouterClient(frontier_client=mock_llm, local_client=local_client, router=router)

    orchestrator = OrchestratorAgent(registry=registry, llm_client=router_client)
    registry.register(orchestrator)

    mcp_agent = MCPAgent(
        agent_id="mcp-get_weather",
        name="MCP Agent - get_weather",
        description="Get weather data",
        tool_name="get_weather",
        tool_schema={},
        mcp_client=mock_mcp_client,
        llm_client=router_client,
    )
    registry.register(mcp_agent)

    app.state.gemini_client = mock_llm
    app.state.local_client = local_client
    app.state.router = router
    app.state.router_client = router_client
    app.state.mcp_client = mock_mcp_client
    app.state.registry = registry
    app.state.orchestrator = orchestrator

    return app


@pytest.fixture
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
