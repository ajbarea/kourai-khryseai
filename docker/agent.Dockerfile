# Generic agent Dockerfile — builds any agent by AGENT_NAME build arg
# Usage: docker build --build-arg AGENT_NAME=mneme -f docker/agent.Dockerfile .
ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS builder

# Install uv and build dependencies
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy workspace root config + lockfile for reproducible builds
COPY pyproject.toml uv.lock ./
COPY shared/ shared/

# Copy agent source (set by build arg)
ARG AGENT_NAME
COPY agents/${AGENT_NAME}/ agents/${AGENT_NAME}/

# Install workspace deps for this agent
RUN uv sync --no-dev --frozen

# --- Runtime stage ---
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG AGENT_NAME
ENV AGENT_NAME=${AGENT_NAME}

WORKDIR /app

# Copy installed venv from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/shared /app/shared
COPY --from=builder /app/agents/${AGENT_NAME} /app/agents/${AGENT_NAME}
COPY --from=builder /app/pyproject.toml /app/pyproject.toml

# Put venv on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Each agent exposes its own port (set via env)
ARG PORT=10000
ENV PORT=${PORT}
EXPOSE ${PORT}

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/.well-known/agent-card.json')" || exit 1

CMD ["sh", "-c", "python -m agents.${AGENT_NAME}"]
