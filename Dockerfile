# =============================================================================
# Stage 1: Build — install dependencies with uv
# =============================================================================
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy project files
COPY pyproject.toml uv.lock ./

# Install dependencies (frozen locks ensure reproducible builds)
RUN uv sync --frozen --no-install-project --no-dev

# Copy source code
COPY . .

# Build the virtual environment with the project included
RUN uv sync --frozen --no-dev


# =============================================================================
# Stage 2: Runner — minimal production image
# =============================================================================
FROM python:3.12-slim AS runner

LABEL org.opencontainers.image.title="AI Platform Agents"
LABEL org.opencontainers.image.description="FastAPI agent execution and MCP tool orchestration service"

# Install runtime utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy the application files
COPY --from=builder /app /app

# Copy the entrypoint and make it executable (done as root)
COPY --from=builder /app/deployment/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create a non-root group and user for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/sh --create-home appuser && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8002

# Docker healthcheck querying the health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
