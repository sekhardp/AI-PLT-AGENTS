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
    assert result.agent_id == "mcp-get_weather"
    assert result.metadata["routed_by"] == "orchestrator-01"
    assert "tool_name" in result.metadata


@pytest.mark.asyncio
async def test_orchestrator_streaming(orchestrator: OrchestratorAgent):
    tokens = []
    async for token in orchestrator.stream("Explain machine learning"):
        tokens.append(token)

    assert len(tokens) > 0
    assert "".join(tokens) == "This is a streamed mock response."
