import pytest
from app.agents.mcp import MCPAgent


@pytest.mark.asyncio
async def test_mcp_agent_execution(mcp_agent: MCPAgent):
    result = await mcp_agent.execute("Check weather for latitude 37.7 and longitude -122.4")
    assert result.agent_id == "mcp-get_weather"
    assert result.agent_name == "MCP Agent - get_weather"
    assert result.metadata["tool_name"] == "get_weather"
    assert "raw_result" in result.metadata
    assert len(result.content) > 0


@pytest.mark.asyncio
async def test_mcp_agent_streaming(mcp_agent: MCPAgent):
    tokens = []
    async for token in mcp_agent.stream("Get weather"):
        tokens.append(token)

    assert len(tokens) > 0
    assert "".join(tokens) == "This is a streamed mock response."
