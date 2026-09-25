import pytest
from app.core.skills import skill_registry


def test_skill_discovery():
    """Verify that SKILL.md for rag-knowledge-base is discovered and parsed."""
    skill_registry.reload_skills()
    rag_skill = skill_registry.get_skill_for_tool("rag_server__search_knowledge_base")
    assert rag_skill is not None
    assert rag_skill["name"] == "rag-knowledge-base"
    assert "rag_server__search_knowledge_base" in rag_skill["tools"]
    assert "SOP" in rag_skill["body"] or "Workflow" in rag_skill["body"]


def test_skills_overview_lightweight():
    """Verify progressive level 1 overview returns concise name and description without full body dump."""
    skill_registry.reload_skills()
    overview = skill_registry.get_skills_overview()
    assert "presentation-storytelling" in overview
    assert "rag-knowledge-base" in overview
    assert "sales-products-analytics" in overview
    # Ensure it's a lightweight overview, not the full 200+ line markdown playbooks
    assert len(overview.splitlines()) >= 3
    assert "### Available Tools" not in overview


def test_relevant_skills_progressive_injection():
    """Verify progressive level 2 dynamic SOP injection based on prompt intent."""
    skill_registry.reload_skills()

    # Generic greeting -> no heavy SOP bodies loaded
    greeting_skills = skill_registry.get_relevant_skills_instructions("Hello, how are you?")
    assert greeting_skills == ""

    # Presentation query -> only presentation-storytelling loaded
    ppt_skills = skill_registry.get_relevant_skills_instructions("Create a 5-slide executive presentation")
    assert "presentation-storytelling" in ppt_skills
    assert "kpi_grid" in ppt_skills
    assert "sales_products" not in ppt_skills

    # Sales & Products query -> only sales-products-analytics loaded
    sales_skills = skill_registry.get_relevant_skills_instructions("Show me top products by revenue in retail stores")
    assert "sales-products-analytics" in sales_skills
    assert "customer-purchase-history" in sales_skills
    assert "presentation-storytelling" not in sales_skills

    # Document RAG query -> rag-knowledge-base loaded
    rag_skills = skill_registry.get_relevant_skills_instructions("Search uploaded documents for refund policy", document_ids=["doc-123"])
    assert "rag-knowledge-base" in rag_skills


def test_all_skills_instructions():
    """Verify aggregated skill instructions are formatted for full compilation scenarios."""
    instructions = skill_registry.get_all_skills_instructions()
    assert "rag-knowledge-base" in instructions
    assert "presentation-storytelling" in instructions
    assert "SlideDeck" in instructions or "Data Storytelling" in instructions


def test_presentation_skill_discovery():
    """Verify presentation storytelling skill is discovered and contains required tool references."""
    skill = skill_registry.get_skill("presentation-storytelling")
    assert skill is not None
    assert skill["name"] == "presentation-storytelling"
    assert "sgs_bq_server__Gold_Executive_Dashboard" in skill["tools"]
    assert "kpi_grid" in skill["body"]


@pytest.mark.asyncio
async def test_load_skill_tool_dynamic_execution():
    """Verify that load_skill tool allows the LLM to fetch full skill instructions at runtime."""
    from unittest.mock import MagicMock

    from app.agents.deps import AgentDeps
    from app.agents.mcp_tools import create_load_skill_tool

    tool = create_load_skill_tool()
    assert tool.name == "load_skill"

    mock_ctx = MagicMock()
    mock_ctx.deps = AgentDeps(skill_registry=skill_registry)

    # Valid skill load
    res = await tool.function(mock_ctx, skill_name="presentation-storytelling")
    assert "Executive Presentation & Data Storytelling Skill" in res
    assert "kpi_grid" in res

    # Fuzzy match skill load (e.g. LLM passes sales_products_analytics or partial name)
    fuzzy_res = await tool.function(mock_ctx, skill_name="sales_products_analytics")
    assert "sales-products-analytics" in fuzzy_res
    assert "sales-products-analytics" in mock_ctx.deps.loaded_skills

    # Non-existent skill returns error with available skills list
    err_res = await tool.function(mock_ctx, skill_name="non-existent-domain")
    assert "Error: Skill 'non-existent-domain' not found" in err_res
    assert "Available skills in directory:" in err_res


@pytest.mark.asyncio
async def test_tool_gating_protocol_enforcement():
    """Verify that domain tools linked to skills are blocked until load_skill is executed."""
    from unittest.mock import AsyncMock, MagicMock

    from app.agents.deps import AgentDeps
    from app.agents.mcp_tools import create_load_skill_tool, create_mcp_tool

    mock_mcp_client = AsyncMock()
    mock_mcp_client.call_tool.return_value = '{"status": "success", "rows": []}'

    deps = AgentDeps(skill_registry=skill_registry, mcp_client=mock_mcp_client)
    mock_ctx = MagicMock()
    mock_ctx.deps = deps

    sales_tool = create_mcp_tool("sales_products_server__execute_sql_query", "Execute query")
    load_skill_tool = create_load_skill_tool()

    # 1. Attempt to execute domain tool BEFORE loading skill -> BLOCKED
    blocked_res = await sales_tool.function(mock_ctx, query="SELECT * FROM products")
    assert "PROTOCOL ENFORCEMENT" in blocked_res
    assert "requires the 'sales-products-analytics' skill playbook" in blocked_res
    assert mock_mcp_client.call_tool.call_count == 0

    # 2. Execute load_skill -> Registers skill in loaded_skills
    load_res = await load_skill_tool.function(mock_ctx, skill_name="sales-products-analytics")
    assert "sales-products-analytics" in load_res
    assert "sales-products-analytics" in deps.loaded_skills

    # 3. Attempt to execute domain tool AFTER loading skill -> ALLOWED
    success_res = await sales_tool.function(mock_ctx, query="SELECT * FROM products")
    assert success_res == '{"status": "success", "rows": []}'
    assert mock_mcp_client.call_tool.call_count == 1


@pytest.mark.asyncio
async def test_generic_tool_executes_without_skill():
    """Verify that generic tools (not associated with any skill) execute immediately without gating."""
    from unittest.mock import AsyncMock, MagicMock

    from app.agents.deps import AgentDeps
    from app.agents.mcp_tools import create_mcp_tool

    mock_mcp_client = AsyncMock()
    mock_mcp_client.call_tool.return_value = "Sunny, 72F"

    deps = AgentDeps(skill_registry=skill_registry, mcp_client=mock_mcp_client)
    mock_ctx = MagicMock()
    mock_ctx.deps = deps

    weather_tool = create_mcp_tool("get_weather", "Get current weather")
    res = await weather_tool.function(mock_ctx, location="San Francisco")
    assert res == "Sunny, 72F"
    assert mock_mcp_client.call_tool.call_count == 1


def test_build_mcp_tools_annotation():
    """Verify build_mcp_tools_from_definitions annotates domain tools with required skill."""
    from app.agents.mcp_tools import build_mcp_tools_from_definitions

    tool_defs = [
        {"name": "sales_products_server__execute_sql_query", "description": "Execute SQL queries"},
        {"name": "get_weather", "description": "Fetch weather"},
    ]
    tools = build_mcp_tools_from_definitions(tool_defs, include_skill_loader=True)

    tool_map = {t.name: t for t in tools}
    assert "load_skill" in tool_map
    assert "PRIORITY TOOL - CALL FIRST" in tool_map["load_skill"].description

    assert "sales_products_server__execute_sql_query" in tool_map
    assert "[REQUIRES SKILL: 'sales-products-analytics']" in tool_map["sales_products_server__execute_sql_query"].description

    assert "get_weather" in tool_map
    assert "[REQUIRES SKILL" not in tool_map["get_weather"].description


def test_weather_skill_discovery_and_gating():
    """Verify weather-air-quality skill is discovered and gates get_current_weather."""
    skill_registry.reload_skills()
    weather_skill = skill_registry.get_skill_for_tool("get_current_weather")
    assert weather_skill is not None
    assert weather_skill["name"] == "weather-air-quality"
    assert "get_current_weather" in weather_skill["tools"]

    weather_server_skill = skill_registry.get_skill_for_tool("weather_server__get_current_weather")
    assert weather_server_skill is not None
    assert weather_server_skill["name"] == "weather-air-quality"


