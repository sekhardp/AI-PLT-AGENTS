set shell := ["bash", "-cu"]

default:
    @just --list

install:
    uv sync

run:
    uv run python -m app.main

serve:
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload

lint:
    uv run python -m compileall app

clean:
    find . -type d -name "__pycache__" -prune -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete

# Use: just test
# Equivalent: uv run pytest

test:
    PYTHONPATH=. uv run pytest -q

docker-build:
    docker build -t ai-plt-agents:latest .

docker-run:
    docker run -it --rm -p 8002:8002 ai-plt-agents:latest
