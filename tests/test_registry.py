from app.agents.base import AgentResult, BaseAgent
from app.agents.registry import AgentRegistry


class DummyAgent(BaseAgent):
    async def execute(self, prompt: str, *, context=None) -> AgentResult:
        return AgentResult(content="Dummy answer", agent_id=self.agent_id, agent_name=self.name)

    async def stream(self, prompt: str, *, context=None):
        yield "Dummy answer"


def test_agent_registration():
    reg = AgentRegistry()
    assert reg.count == 0

    agent1 = DummyAgent(
        agent_id="agent-01",
        name="Agent 1",
        description="First test agent",
        capabilities=["data-analysis", "sql"],
    )
    reg.register(agent1)

    assert reg.count == 1
    assert reg.get("agent-01") is agent1
    assert reg.get_by_name("Agent 1") is agent1
    assert reg.get_by_capability("sql") == [agent1]
    assert reg.get_by_capability("nonexistent") == []

    health = reg.health()
    assert health["total_agents"] == 1
    assert health["agents"][0]["agent_id"] == "agent-01"

    assert reg.unregister("agent-01") is True
    assert reg.count == 0
    assert reg.unregister("agent-01") is False
