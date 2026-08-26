from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.distribution import APP_DISTRIBUTION, APP_VERSION
from app.core.error import register_error_handlers
from app.core.logging import setup_logging
from app.core.settings import app_settings
from app.api.router import root_router
from app.clients.gemini_client import GeminiClient
from app.clients.mcp_client import MCPRegistryClient
from app.agents.registry import AgentRegistry
from app.agents.orchestrator import OrchestratorAgent
from app.agents.mcp import MCPAgent

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager managing startup initialization and shutdown."""
    setup_logging()

    logger.info(
        "agent_service_starting",
        app_name=app_settings.NAME,
        env=app_settings.ENV,
        gcp_project=app_settings.vertex_settings.GCP_PROJECT_ID,
        gcp_location=app_settings.vertex_settings.GCP_LOCATION,
        model=app_settings.vertex_settings.GEMINI_MODEL,
        mcp_registry_url=app_settings.mcp_settings.REGISTRY_URL,
    )

    # Initialize Gemini LLM Client
    gemini_client = GeminiClient(
        project_id=app_settings.vertex_settings.GCP_PROJECT_ID,
        location=app_settings.vertex_settings.GCP_LOCATION,
        model_name=app_settings.vertex_settings.GEMINI_MODEL,
        default_temperature=app_settings.vertex_settings.GEMINI_TEMPERATURE,
        default_max_tokens=app_settings.vertex_settings.GEMINI_MAX_TOKENS,
    )

    # Initialize Agent Registry
    registry = AgentRegistry()

    # Initialize and Register Master Orchestrator Agent
    orchestrator = OrchestratorAgent(registry=registry, llm_client=gemini_client)
    registry.register(orchestrator)

    # Initialize MCP Registry Client and discover tools
    mcp_client = MCPRegistryClient(
        registry_url=app_settings.mcp_settings.REGISTRY_URL,
        timeout_seconds=app_settings.mcp_settings.TIMEOUT_SECONDS,
    )

    try:
        tools = await mcp_client.list_tools()
        for tool in tools:
            tool_name = tool["name"]
            mcp_agent = MCPAgent(
                agent_id=f"mcp-{tool_name}",
                name=f"MCP Agent - {tool_name}",
                description=tool.get("description", f"Tool: {tool_name}"),
                tool_name=tool_name,
                tool_schema=tool.get("input_schema", {}),
                mcp_client=mcp_client,
                llm_client=gemini_client,
            )
            registry.register(mcp_agent)
        logger.info("mcp_tools_registration_complete", count=len(tools))
    except Exception as e:
        logger.warning("mcp_tools_discovery_warning", error=str(e))

    # Attach shared instances to FastAPI application state
    app.state.gemini_client = gemini_client
    app.state.mcp_client = mcp_client
    app.state.registry = registry
    app.state.orchestrator = orchestrator

    logger.info("agent_service_ready", total_registered_agents=registry.count)

    yield

    logger.info("agent_service_shutting_down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=app_settings.NAME,
        version=app_settings.VERSION,
        description=app_settings.DESCRIPTION,
        lifespan=lifespan,
    )

    # Configure CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.endpoint_settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Exception Handlers
    register_error_handlers(app)

    # Mount Root Router
    app.include_router(root_router)

    return app


def bootstrap() -> FastAPI:
    """Bootstrap the FastAPI application."""
    return create_app()
