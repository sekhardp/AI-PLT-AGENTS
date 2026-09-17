import logging
import sys

import logfire
import structlog

from app.core.settings import app_settings


def setup_logfire() -> None:
    """Configures Pydantic Logfire observability and tracing.
    
    Suppresses noisy internal Pydantic validation micro-spans while retaining
    high-level agent runs, LLM calls, tool execution responses, and error traces.
    """
    lf_settings = app_settings.logfire_settings
    send_to_logfire = (
        lf_settings.SEND_TO_LOGFIRE
        if lf_settings.SEND_TO_LOGFIRE is not None
        else ("if-token-present" if lf_settings.TOKEN else False)
    )

    console_opt = False if (not lf_settings.CONSOLE or app_settings.is_production) else None

    logfire.configure(
        token=lf_settings.TOKEN,
        service_name=lf_settings.SERVICE_NAME,
        service_version=lf_settings.SERVICE_VERSION,
        environment=lf_settings.ENVIRONMENT or app_settings.ENV,
        send_to_logfire=send_to_logfire,
        console=console_opt,
        pydantic_plugin=None,  # Suppress noisy Pydantic schema validation micro-spans
    )
    # Retain high-level agent runs, LLM calls, tool executions, and HTTP traces
    logfire.instrument_pydantic_ai()
    logfire.instrument_httpx()


def setup_logging() -> None:
    """Configures structured logging and Logfire for the application."""
    log_level_name = app_settings.logging_settings.LEVEL.upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    setup_logfire()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
            if app_settings.logging_settings.JSON_FORMAT_ENABLED
            else structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger(__name__)
