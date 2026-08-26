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
