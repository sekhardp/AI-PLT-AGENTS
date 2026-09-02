from app.core.settings import (
    AppSettings,
    EndpointSettings,
    LocalLLMSettings,
    RouterSettings,
    VertexAISettings,
)


def test_settings_initialization():
    settings = AppSettings()
    assert settings.NAME.lower() == "ai-plt-agents"
    assert settings.VERSION == "0.1.0"
    assert settings.endpoint_settings.PORT == 8002
    assert settings.vertex_settings.GEMINI_MODEL == "gemini-2.5-flash"
    assert settings.mcp_settings.REGISTRY_URL.endswith("/sse")
    assert settings.local_llm_settings.MODEL == "Qwen/Qwen2.5-7B-Instruct"
    assert settings.router_settings.DEFAULT_STRATEGY == "AUTO"


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


def test_local_llm_and_router_settings():
    local_cfg = LocalLLMSettings(
        BASE_URL="http://10.128.0.5:8000/v1",
        MODEL="meta-llama/Meta-Llama-3.1-8B-Instruct",
        TIMEOUT_SECONDS=120,
    )
    assert local_cfg.BASE_URL == "http://10.128.0.5:8000/v1"
    assert local_cfg.MODEL == "meta-llama/Meta-Llama-3.1-8B-Instruct"
    assert local_cfg.TIMEOUT_SECONDS == 120

    router_cfg = RouterSettings(
        DEFAULT_STRATEGY="LOCAL_FIRST",
        COMPLEXITY_THRESHOLD=0.65,
        FALLBACK_ENABLED=True,
    )
    assert router_cfg.DEFAULT_STRATEGY == "LOCAL_FIRST"
    assert router_cfg.COMPLEXITY_THRESHOLD == 0.65
    assert router_cfg.FALLBACK_ENABLED is True
