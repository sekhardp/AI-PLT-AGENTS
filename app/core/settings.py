from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .distribution import APP_DISTRIBUTION, APP_VERSION


class LoggingSettings(BaseSettings):
    """Logging settings for the application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        env_prefix="LOGGING_",
        extra="ignore",
    )

    LEVEL: str = Field("INFO", description="Logging level (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    JSON_FORMAT_ENABLED: bool = Field(False, description="Enable JSON logging format")


class EndpointSettings(BaseSettings):
    """Endpoint settings for the FastAPI server."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        env_prefix="ENDPOINT_",
        extra="ignore",
    )

    HOST: str = Field("0.0.0.0", description="Service bind host")
    PORT: int = Field(8002, description="Service bind port")
    ALLOWED_ORIGINS: list[str] = Field(default_factory=lambda: ["*"], description="Allowed CORS origins")


class VertexAISettings(BaseSettings):
    """Google Cloud Vertex AI and Gemini model settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    GCP_PROJECT_ID: str = Field("beam-suntory-gemini-llm-poc", description="GCP Project ID for Vertex AI")
    GCP_LOCATION: str = Field("us-central1", description="GCP region for Vertex AI endpoints")
    GEMINI_MODEL: str = Field("gemini-2.5-flash", description="Gemini model identifier")
    GEMINI_TEMPERATURE: float = Field(0.7, description="Sampling temperature for LLM generation")
    GEMINI_MAX_TOKENS: int = Field(4096, description="Max output tokens for LLM generation")


class MCPSettings(BaseSettings):
    """Model Context Protocol (MCP) Registry and Gateway settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        env_prefix="MCP_",
        extra="ignore",
    )

    REGISTRY_URL: str = Field("http://localhost:8081/sse", description="MCP Registry Gateway SSE URL")
    TIMEOUT_SECONDS: int = Field(60, description="Timeout for MCP tool executions")


class LocalLLMSettings(BaseSettings):
    """Local LLM instance settings (vLLM, Ollama, or OpenAI-compatible endpoint)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        env_prefix="LOCAL_LLM_",
        extra="ignore",
    )

    BASE_URL: str = Field("http://localhost:8000/v1", description="Local LLM service OpenAI-compatible base URL")
    MODEL: str = Field("Qwen/Qwen2.5-7B-Instruct", description="Default model name hosted on the local instance")
    API_KEY: str | None = Field(None, description="Optional API key for authenticated local endpoints")
    TIMEOUT_SECONDS: int = Field(60, description="Timeout for local LLM requests in seconds")
    TEMPERATURE: float = Field(0.7, description="Default sampling temperature for local LLM")
    MAX_TOKENS: int = Field(4096, description="Default max output tokens for local LLM")
    ENABLED: bool = Field(True, description="Whether local LLM routing is enabled")


class RouterSettings(BaseSettings):
    """Smart AI Router settings for navigating between Local LLM and Frontier Model."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        env_prefix="ROUTER_",
        extra="ignore",
    )

    DEFAULT_STRATEGY: str = Field(
        "AUTO",
        description="Default routing strategy: AUTO, LOCAL_FIRST, FRONTIER_FIRST, LOCAL_ONLY, FRONTIER_ONLY",
    )
    COMPLEXITY_THRESHOLD: float = Field(
        0.55,
        description="Complexity score threshold (0.0 to 1.0) above which queries route to Frontier Model",
    )
    FALLBACK_ENABLED: bool = Field(
        True,
        description="Enable automatic fallback to Frontier Model when Local LLM fails or is unreachable",
    )


class AppSettings(BaseSettings):
    """Application settings for the AI Platform Agents Service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        env_prefix="APP_",
        extra="ignore",
    )

    NAME: str = Field(APP_DISTRIBUTION.name, description="Application name")
    VERSION: str = Field(APP_VERSION, description="Application version")
    DESCRIPTION: str = Field(APP_DISTRIBUTION.description, description="Application description")
    ENV: str = Field("development", description="Runtime environment (development, staging, production)")

    logging_settings: LoggingSettings = Field(default_factory=LoggingSettings)
    endpoint_settings: EndpointSettings = Field(default_factory=EndpointSettings)
    vertex_settings: VertexAISettings = Field(default_factory=VertexAISettings)
    mcp_settings: MCPSettings = Field(default_factory=MCPSettings)
    local_llm_settings: LocalLLMSettings = Field(default_factory=LocalLLMSettings)
    router_settings: RouterSettings = Field(default_factory=RouterSettings)

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.ENV.lower() == "development"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()


app_settings = get_settings()
