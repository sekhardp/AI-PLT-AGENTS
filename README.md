# AI Platform Agents Service (`AI-PLT-AGENTS`)

Production-grade agent execution and Model Context Protocol (MCP) orchestration service powered by Google Gemini on Vertex AI.

---

## Features

- **Google Gemini 2.5 Flash on Vertex AI**: Direct integration using the modern `google-genai` SDK with streaming and async generation.
- **Dynamic MCP Tool Orchestration**: Automatic tool discovery and execution via the MCP Registry Gateway SSE interface.
- **Master Orchestrator Agent**: Intelligent intent classification, tool routing, and answer synthesis.
- **Production Architecture**: Layered architecture (`core`, `clients`, `agents`, `api/v1`) matching `AI-PLT-BE`.
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
| `GET` | `/health` / `/api/v1/health` | Service and registered agents health check |
| `GET` | `/agents` / `/api/v1/agents` | List all registered agents and capabilities |
| `GET` | `/agents/{id}` / `/api/v1/agents/{id}` | Retrieve specific agent metadata |
| `POST` | `/execute` / `/api/v1/execute` | Execute agent prompt (synchronous or SSE streaming) |

---

## Deployment to Google Cloud Run

To build and deploy using Google Cloud Build:
```bash
gcloud builds submit --config=deployment/cloudbuild.yaml .
```
