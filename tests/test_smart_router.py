import pytest
from app.clients.router_client import SmartRouterClient
from app.router.smart_router import ComplexityScorer, RoutingStrategy, SmartAIRouter
from tests.conftest import MockLLMClient


def test_complexity_scorer_simple_prompts():
    scorer = ComplexityScorer(threshold=0.55)
    score_hello = scorer.score("Hello there!")
    assert score_hello < 0.40

    score_summary = scorer.score("Summarize in 1 sentence: The sky is blue because of Rayleigh scattering.")
    assert score_summary < 0.55

    score_grammar = scorer.score("Fix the grammar in this text: He go to school yesterday.")
    assert score_grammar < 0.50


def test_complexity_scorer_complex_prompts():
    scorer = ComplexityScorer(threshold=0.55)
    complex_prompt = (
        "Analyze the system design and architect a distributed consensus protocol using Paxos, "
        "synthesizing fault tolerance, evaluating trade-offs, and avoiding race conditions."
    )
    score_complex = scorer.score(complex_prompt)
    assert score_complex > 0.65

    # Code snippet detection
    code_prompt = "```python\ndef solve_paxos():\n    pass\n```\nAnalyze root cause analysis and refactor architecture."
    assert scorer.score(code_prompt) > 0.60


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
