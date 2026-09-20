import pytest
from app.agents.mcp import MCPAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.registry import AgentRegistry


@pytest.mark.asyncio
async def test_orchestrator_direct_execution(orchestrator: OrchestratorAgent):
    result = await orchestrator.execute("Explain quantum computing")
    assert result.agent_id == "orchestrator-01"
    assert result.agent_name == "Agent Orchestrator"
    assert len(result.content) > 0
    assert result.metadata["routed_to"] is None


@pytest.mark.asyncio
async def test_orchestrator_delegation_to_mcp(
    orchestrator: OrchestratorAgent,
    registry: AgentRegistry,
    mcp_agent: MCPAgent,
):
    registry.register(mcp_agent)

    result = await orchestrator.execute("What is the weather in San Francisco?")
    assert result.agent_id == "orchestrator-01"
    assert len(result.metadata.get("executed_tools", [])) > 0
    assert result.metadata["executed_tools"][0]["tool_name"] == "get_weather"


@pytest.mark.asyncio
async def test_orchestrator_streaming(orchestrator: OrchestratorAgent):
    tokens = []
    async for token in orchestrator.stream("Explain machine learning"):
        tokens.append(token)

    assert len(tokens) > 0
    assert "".join(tokens) == "This is a streamed mock response."


@pytest.mark.asyncio
async def test_orchestrator_local_only_offline_failure(registry: AgentRegistry):
    from tests.conftest import MockLLMClient

    class FailingLocalClient(MockLLMClient):
        async def generate(self, *args, **kwargs):
            raise ConnectionError("Local vLLM instance connection refused")

        async def stream(self, *args, **kwargs):
            raise ConnectionError("Local vLLM stream connection refused")
            yield  # pragma: no cover

    from app.clients.router_client import SmartRouterClient
    from app.router.smart_router import RoutingStrategy, SmartAIRouter

    frontier = MockLLMClient(fixed_response="Frontier Response")
    failing_local = FailingLocalClient()
    router = SmartAIRouter(default_strategy=RoutingStrategy.LOCAL_ONLY, fallback_enabled=True)
    router_client = SmartRouterClient(frontier_client=frontier, local_client=failing_local, router=router)
    orch = OrchestratorAgent(registry=registry, llm_client=router_client)

    # 1. Execute under LOCAL_ONLY -> Raises ConnectionError without falling back
    with pytest.raises(ConnectionError, match="Local LLM instance is offline or unreachable"):
        await orch.execute("Hello local", context={"routing_strategy": "LOCAL_ONLY"})

    # 2. Stream under LOCAL_ONLY -> Yields error message without falling back
    stream_events = []
    async for event in orch.stream("Hello local", context={"routing_strategy": "LOCAL_ONLY"}):
        stream_events.append(event)

    error_events = [e for e in stream_events if isinstance(e, str) and "Error: Local LLM instance is offline or unreachable" in e]
    assert len(error_events) > 0


@pytest.mark.asyncio
async def test_orchestrator_auto_stream_fallback(registry: AgentRegistry):
    from tests.conftest import MockLLMClient

    class FailingLocalClient(MockLLMClient):
        async def generate(self, *args, **kwargs):
            raise ConnectionError("Local vLLM instance connection refused")

        async def stream(self, *args, **kwargs):
            raise ConnectionError("Local vLLM stream connection refused")
            yield  # pragma: no cover

    from app.clients.router_client import SmartRouterClient
    from app.router.smart_router import RoutingStrategy, SmartAIRouter

    frontier = MockLLMClient(fixed_response="Frontier Response")
    failing_local = FailingLocalClient()
    router = SmartAIRouter(default_strategy=RoutingStrategy.AUTO, fallback_enabled=True)
    router_client = SmartRouterClient(frontier_client=frontier, local_client=failing_local, router=router)
    orch = OrchestratorAgent(registry=registry, llm_client=router_client)

    context = {"routing_strategy": "AUTO"}
    events = []
    async for e in orch.stream("Hello simple query", context=context):
        events.append(e)

    # Verify fallback occurred and stream completed successfully
    assert context["fallback_triggered"] is True
    assert context["routed_to"] == "frontier"
    assert len(events) > 0
    token_strings = [e for e in events if isinstance(e, str)]
    assert "streamed mock response" in "".join(token_strings)

