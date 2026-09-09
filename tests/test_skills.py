from app.core.skills import skill_registry


def test_skill_discovery():
    """Verify that SKILL.md for rag-knowledge-base is discovered and parsed."""
    skill_registry.reload_skills()
    rag_skill = skill_registry.get_skill_for_tool("rag_server__search_knowledge_base")
    assert rag_skill is not None
    assert rag_skill["name"] == "rag-knowledge-base"
    assert "rag_server__search_knowledge_base" in rag_skill["tools"]
    assert "SOP" in rag_skill["body"] or "Workflow" in rag_skill["body"]


def test_all_skills_instructions():
    """Verify aggregated skill instructions are formatted for system prompts."""
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

