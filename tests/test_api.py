import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient):
    # Test root alias /health
    res_root = await client.get("/health")
    assert res_root.status_code == 200
    data_root = res_root.json()
    assert data_root["status"] == "ok"
    assert data_root["service"] == "ai-plt-agents"

    # Test v1 endpoint /api/v1/health
    res_v1 = await client.get("/api/v1/health")
    assert res_v1.status_code == 200
    data_v1 = res_v1.json()
    assert data_v1["status"] == "ok"
    assert data_v1["agents"]["total_agents"] >= 1


@pytest.mark.asyncio
async def test_agents_endpoints(client: AsyncClient):
    # List agents
    res = await client.get("/api/v1/agents")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 2
    agent_ids = [a["agent_id"] for a in data["agents"]]
    assert "orchestrator-01" in agent_ids
    assert "mcp-get_weather" in agent_ids

    # Get single agent
    res_single = await client.get("/api/v1/agents/orchestrator-01")
    assert res_single.status_code == 200
    assert res_single.json()["name"] == "Agent Orchestrator"

    # Get nonexistent agent
    res_404 = await client.get("/api/v1/agents/unknown-agent")
    assert res_404.status_code == 404

    # Sync agents
    res_sync = await client.post("/api/v1/agents/sync")
    assert res_sync.status_code == 200
    data_sync = res_sync.json()
    assert data_sync["status"] == "ok"
    assert data_sync["discovered_tools_count"] >= 1


@pytest.mark.asyncio
async def test_execute_endpoint(client: AsyncClient):
    # Synchronous execution with strategy override
    payload = {"prompt": "Hello AI platform", "routing_strategy": "LOCAL_ONLY"}
    res = await client.post("/api/v1/execute", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["agent_id"] == "orchestrator-01"
    assert len(data["content"]) > 0
    assert "trace_id" in data
    assert data["metadata"]["routed_to"] == "local"
    assert data["metadata"]["routing_strategy"] == "LOCAL_ONLY"
    assert data["total_tokens"] is not None
    assert data["total_tokens"] > 0
    assert "usage" in data
    assert data["usage"]["total_tokens"] > 0


@pytest.mark.asyncio
async def test_execute_streaming_endpoint(client: AsyncClient):
    payload = {"prompt": "Count to 5", "stream": True}
    res = await client.post("/api/v1/execute", json=payload)
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]
    text = res.text
    assert "data: " in text
    assert '"done": true' in text.lower()
    assert '"total_tokens":' in text
    assert '"usage":' in text


@pytest.mark.asyncio
async def test_router_endpoints(client: AsyncClient):
    # 1. Router status
    res_status = await client.get("/api/v1/router/status")
    assert res_status.status_code == 200
    data_status = res_status.json()
    assert data_status["status"] == "ok"
    assert "router" in data_status
    assert "default_strategy" in data_status["router"]

    # 2. Router classify
    classify_payload = {
        "prompt": "Analyze race conditions in distributed systems and write a formal verification mathematical proof."
    }
    res_classify = await client.post("/api/v1/router/classify", json=classify_payload)
    assert res_classify.status_code == 200
    data_classify = res_classify.json()
    assert data_classify["target"] == "frontier"
    assert data_classify["complexity_score"] >= 0.55

    # 3. Router update strategy
    strategy_payload = {"strategy": "LOCAL_FIRST", "complexity_threshold": 0.70}
    res_strategy = await client.post("/api/v1/router/strategy", json=strategy_payload)
    assert res_strategy.status_code == 200
    data_strat = res_strategy.json()
    assert data_strat["updated_strategy"] == "LOCAL_FIRST"
    assert data_strat["updated_threshold"] == 0.70

