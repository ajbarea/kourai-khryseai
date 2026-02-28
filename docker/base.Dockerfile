# Base image for all Kourai Khryseai agents
# Multi-stage build: deps → runtime
FROM python:3.12-slim AS base

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy workspace root + shared lib first (changes less often → better layer caching)
COPY pyproject.toml uv.lock ./
COPY shared/ shared/

# Sync shared deps only (cached layer)
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# Health check hits the A2A agent card endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-10000}/.well-known/agent.json')" || exit 1
