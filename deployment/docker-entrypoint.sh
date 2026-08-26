#!/bin/sh
# docker-entrypoint.sh
#
# Runs before uvicorn starts inside the container.

set -e

PORT="${PORT:-${ENDPOINT_PORT:-8002}}"

echo "========================================="
echo " AI Platform Agents (AI-PLT-AGENTS)      "
echo "========================================="
echo " Environment     : ${APP_ENV:-development}"
echo " GCP Project ID  : ${GCP_PROJECT_ID:-beam-suntory-gemini-llm-poc}"
echo " GCP Location    : ${GCP_LOCATION:-us-central1}"
echo " Gemini Model    : ${GEMINI_MODEL:-gemini-2.5-flash}"
echo " MCP Registry URL: ${MCP_REGISTRY_URL:-http://localhost:8081/sse}"
echo " Log Level       : ${LOGGING_LEVEL:-info}"
echo " Port            : ${PORT}"
echo "========================================="

# Execute Uvicorn replacing shell process (PID 1)
exec uvicorn app.main:app \
    --host "${ENDPOINT_HOST:-0.0.0.0}" \
    --port "${PORT}" \
    --log-level "${LOGGING_LEVEL:-info}" \
    --no-access-log
