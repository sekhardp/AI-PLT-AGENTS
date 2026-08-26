from app.core.settings import AppSettings, LoggingSettings, EndpointSettings, VertexAISettings, MCPSettings


def test_settings_initialization():
    settings = AppSettings()
    assert settings.NAME.lower() == "ai-plt-agents"
    assert settings.VERSION == "0.1.0"
    assert settings.endpoint_settings.PORT == 8002
    assert settings.vertex_settings.GEMINI_MODEL == "gemini-2.5-flash"
    assert settings.mcp_settings.REGISTRY_URL == "http://localhost:8081/sse"


def test_custom_endpoint_settings():
    endpoint = EndpointSettings(HOST="127.0.0.1", PORT=9000)
    assert endpoint.HOST == "127.0.0.1"
    assert endpoint.PORT == 9000


def test_vertex_settings():
    vertex = VertexAISettings(
        GCP_PROJECT_ID="test-project",
        GCP_LOCATION="us-central1",
        GEMINI_MODEL="gemini-2.0-flash",
    )
    assert vertex.GCP_PROJECT_ID == "test-project"
    assert vertex.GEMINI_MODEL == "gemini-2.0-flash"
