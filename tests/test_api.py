import json
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


@pytest.mark.asyncio
async def test_execute_endpoint(client: AsyncClient):
    # Synchronous execution
    payload = {"prompt": "Hello AI platform"}
    res = await client.post("/api/v1/execute", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["agent_id"] == "orchestrator-01"
    assert len(data["content"]) > 0
    assert "trace_id" in data


@pytest.mark.asyncio
async def test_execute_streaming_endpoint(client: AsyncClient):
    payload = {"prompt": "Count to 5", "stream": True}
    res = await client.post("/api/v1/execute", json=payload)
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]
    text = res.text
    assert "data: " in text
    assert '"done": true' in text.lower()
