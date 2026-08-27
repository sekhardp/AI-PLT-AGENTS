# AI Platform Agents Service (`AI-PLT-AGENTS`)

Production-grade agent execution and Model Context Protocol (MCP) orchestration service powered by Google Gemini on Vertex AI.

---

## Features

- **Google Gemini 2.5 Flash on Vertex AI**: Direct integration using the modern `google-genai` SDK with streaming and async generation (Frontier Model).
- **Self-Hosted Local LLM (vLLM)**: High-throughput OpenAI-compatible inference on a dedicated GCP Compute Engine GPU instance (`g2-standard-4` with NVIDIA L4).
- **Smart AI Router**: Intelligently analyzes prompt complexity, length, and task intent to dynamically route requests between Local LLM and Frontier Gemini.
- **Resilient Circuit Breaker & Zero Downtime Failover**: Automatically escalates to Frontier Gemini if the local instance is offline or errors.
- **Dynamic MCP Tool Orchestration**: Automatic tool discovery and execution via the MCP Registry Gateway SSE interface.
- **Master Orchestrator Agent**: Intelligent intent classification, tool routing, and answer synthesis.
- **Production Architecture**: Layered architecture (`core`, `clients`, `agents`, `router`, `api/v1`) matching `AI-PLT-BE`.
- **Cloud Run Deployment**: Ready-to-deploy multi-stage `Dockerfile` and `cloudbuild.yaml` with Google Artifact Registry integration.

---

## Quickstart

### Prerequisites
- Python 3.12+
- `uv` package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Google Cloud SDK (`gcloud auth application-default login`)

### Setup & Run Locally
```bash
# 1. Install dependencies
just install

# 2. Copy and configure environment variables
cp .env.example .env

# 3. Run the development server (port 8002)
just run
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` / `/api/v1/health` | Service, agents, router, and model health check |
| `GET` | `/agents` / `/api/v1/agents` | List all registered agents and capabilities |
| `GET` | `/agents/{id}` / `/api/v1/agents/{id}` | Retrieve specific agent metadata |
| `POST` | `/execute` / `/api/v1/execute` | Execute agent prompt with Smart Routing (or explicit strategy override) |
| `GET` | `/api/v1/router/status` | Real-time router status, circuit breaker, and model liveness |
| `POST` | `/api/v1/router/classify` | Preview complexity score and predicted route without executing LLM |
| `POST` | `/api/v1/router/strategy` | Dynamically update active routing strategy or complexity threshold |

---

## Dedicated vLLM Service (`ai-plt-local-llm`)

For hosting the local LLM on Google Compute Engine or GPU instances, see the standalone repository [`ai-plt-local-llm`](../ai-plt-local-llm).

---

## Deployment to Google Cloud Run

To build and deploy using Google Cloud Build:
```bash
gcloud builds submit --config=deployment/cloudbuild.yaml .
```
