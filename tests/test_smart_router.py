import pytest
from app.clients.router_client import SmartRouterClient
from app.router.smart_router import RoutingStrategy, SmartAIRouter
from tests.conftest import MockLLMClient


def test_smart_ai_router_auto_strategy():
    router = SmartAIRouter(default_strategy=RoutingStrategy.AUTO, complexity_threshold=0.55)

    decision_simple = router.classify("Hello, what is the capital of France?")
    assert decision_simple.target == "local"
    assert decision_simple.strategy == RoutingStrategy.AUTO

    decision_complex = router.classify(
        "Analyze race conditions in distributed systems and write a formal verification mathematical proof."
    )
    assert decision_complex.target == "frontier"
    assert decision_complex.complexity_score >= 0.55


def test_smart_ai_router_strategies():
    router = SmartAIRouter(default_strategy=RoutingStrategy.AUTO)

    # LOCAL_ONLY
    dec_local = router.classify("Any complex analysis query", strategy_override="LOCAL_ONLY")
    assert dec_local.target == "local"

    # FRONTIER_ONLY
    dec_frontier = router.classify("Hello", strategy_override="FRONTIER_ONLY")
    assert dec_frontier.target == "frontier"

    # Context strategy override
    dec_ctx = router.classify("Hello", context={"routing_strategy": "FRONTIER_ONLY"})
    assert dec_ctx.target == "frontier"


def test_smart_ai_router_circuit_breaker():
    router = SmartAIRouter(default_strategy=RoutingStrategy.AUTO, fallback_enabled=True)
    assert router.is_local_available is True

    # Record 3 failures
    router.record_local_failure(RuntimeError("Connection timeout 1"))
    router.record_local_failure(RuntimeError("Connection timeout 2"))
    router.record_local_failure(RuntimeError("Connection timeout 3"))

    assert router.is_local_available is False

    # Simple prompt would normally go to local, but circuit is tripped
    decision = router.classify("Hello!")
    assert decision.target == "frontier"
    assert "circuit_breaker" in decision.reason

    # Recovery
    router.record_local_success()
    assert router.is_local_available is True
    assert router.classify("Hello!").target == "local"


@pytest.mark.asyncio
async def test_smart_router_client_execution():
    frontier = MockLLMClient(fixed_response="Frontier Answer")
    frontier.provider_name = "mock-frontier"
    local = MockLLMClient(fixed_response="Local Answer")
    local.provider_name = "mock-local"

    router = SmartAIRouter(default_strategy=RoutingStrategy.AUTO, complexity_threshold=0.55)
    client = SmartRouterClient(frontier_client=frontier, local_client=local, router=router)

    # 1. Simple query -> Routed to Local
    res_local = await client.generate("Hello there!")
    assert res_local.metadata["routed_to"] == "local"
    assert "Local Answer" in res_local.content
    assert res_local.metadata["fallback_triggered"] is False

    # 2. Complex query -> Routed to Frontier
    res_frontier = await client.generate(
        "Analyze distributed consensus, architect a fault tolerant Paxos, and evaluate trade-offs."
    )
    assert res_frontier.metadata["routed_to"] == "frontier"
    assert "Frontier Answer" in res_frontier.content


@pytest.mark.asyncio
async def test_smart_router_client_fallback():
    class FailingLocalClient(MockLLMClient):
        async def generate(self, *args, **kwargs):
            raise ConnectionError("Local vLLM instance connection refused")

        async def stream(self, *args, **kwargs):
            raise ConnectionError("Local vLLM stream connection refused")
            yield  # pragma: no cover

    frontier = MockLLMClient(fixed_response="Frontier Fallback Answer")
    failing_local = FailingLocalClient()
    router = SmartAIRouter(default_strategy=RoutingStrategy.AUTO, fallback_enabled=True)
    client = SmartRouterClient(frontier_client=frontier, local_client=failing_local, router=router)

    # Query targets local, but fails -> seamless fallback to Frontier!
    res = await client.generate("Hello there!")
    assert res.metadata["routed_to"] == "frontier"
    assert res.metadata["fallback_triggered"] is True
    assert "Frontier Fallback Answer" in res.content

    # Streaming fallback
    tokens = []
    async for t in client.stream("Hello again!"):
        tokens.append(t)
    assert len(tokens) > 0


@pytest.mark.asyncio
async def test_smart_router_llm_decide():
    # 1. Local LLM classifies as simple -> target: local
    local_classifier = MockLLMClient(fixed_response='{"target": "local", "reason": "simple greeting"}')
    router = SmartAIRouter(local_client=local_classifier)
    decision = await router.decide("Hello!")
    assert decision.target == "local"
    assert decision.reason == "simple greeting"

    # 2. Local LLM classifies as complex -> target: frontier
    local_classifier.fixed_response = '{"target": "frontier", "reason": "deep reasoning required"}'
    decision_frontier = await router.decide("Architect distributed consensus system")
    assert decision_frontier.target == "frontier"
    assert decision_frontier.reason == "deep reasoning required"


@pytest.mark.asyncio
async def test_smart_router_llm_decide_unreachable_fallback():
    class OfflineLocalClient(MockLLMClient):
        async def generate(self, *args, **kwargs):
            raise ConnectionError("Compute Engine VM is stopped (connect timed out)")

    offline_client = OfflineLocalClient()
    router = SmartAIRouter(local_client=offline_client, fallback_enabled=True)

    # Local is down -> immediately and gracefully falls back to frontier!
    decision = await router.decide("What is the weather today?")
    assert decision.target == "frontier"
    assert "local_unreachable_fallback" in decision.reason
    assert decision.metadata["fallback_triggered"] is True

