# Kourai Khryseai — Consolidated host Dockerfile
#
# Usage:
#   docker build --build-arg HOST_TYPE=agent --build-arg PACKAGE_NAME=mneme -f docker/host.Dockerfile .
#   docker build --build-arg HOST_TYPE=gui --build-arg PACKAGE_NAME=gui -f docker/host.Dockerfile .
#   docker build --build-arg HOST_TYPE=cli --build-arg PACKAGE_NAME=cli -f docker/host.Dockerfile .

# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.12

# --- Builder ---
FROM python:${PYTHON_VERSION}-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.10.10 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY shared/ shared/
COPY scripts/ scripts/

ARG HOST_TYPE
ARG PACKAGE_NAME

# Copies all agent/host source but only installs the target package via --package.
COPY agents/ agents/
COPY hosts/ hosts/

RUN uv sync --package kourai-${PACKAGE_NAME} --no-dev --frozen

# --- Runtime ---
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG PYTHON_VERSION=3.12
ARG HOST_TYPE
ARG PACKAGE_NAME
ARG PORT=10000

ENV HOST_TYPE=${HOST_TYPE} \
    PACKAGE_NAME=${PACKAGE_NAME} \
    PORT=${PORT} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Agent/CLI: git for project context, curl for health checks
RUN if [ "${HOST_TYPE}" = "agent" ] || [ "${HOST_TYPE}" = "cli" ]; then \
    apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*; \
    fi

# GUI: SDL2 runtime libs for pygame
RUN if [ "${HOST_TYPE}" = "gui" ]; then \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    libsdl2-2.0-0 \
    libsdl2-image-2.0-0 \
    libsdl2-mixer-2.0-0 \
    libsdl2-ttf-2.0-0 \
    libfreetype6 && \
    rm -rf /var/lib/apt/lists/*; \
    fi

COPY --from=builder /app/.venv /app/.venv
COPY agents/ agents/
COPY hosts/ hosts/
COPY shared/ shared/
COPY scripts/ scripts/
COPY assets/ assets/
COPY templates/ templates/
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd -m -u 1000 kourai && chown -R kourai:kourai /app
USER kourai

EXPOSE ${PORT}

ENTRYPOINT ["/app/entrypoint.sh"]

LABEL org.opencontainers.image.title="Kourai Khryseai — ${HOST_TYPE}" \
    org.opencontainers.image.description="Multi-agent A2A development system — ${PACKAGE_NAME}" \
    org.opencontainers.image.url="https://github.com/ajbarea/kourai_khryseai"
