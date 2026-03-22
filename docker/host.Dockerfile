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

COPY --link pyproject.toml uv.lock ./
COPY --link shared/ shared/
COPY --link scripts/ scripts/

ARG HOST_TYPE
ARG PACKAGE_NAME

# Copies all agent/host source but only installs the target package via --package.
COPY --link agents/ agents/
COPY --link hosts/ hosts/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package kourai-${PACKAGE_NAME} --no-dev --frozen

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

# Dokimasia: Chromium + Playwright for E2E frontend testing (Phase E4)
RUN if [ "${HOST_TYPE}" = "agent" ] && [ "${PACKAGE_NAME}" = "dokimasia" ]; then \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    chromium \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libgbm1 \
    libgcc-s1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++-12-dev \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxinerama1 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    xdg-utils && \
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

COPY --link --from=builder /app/.venv /app/.venv
COPY --link agents/ agents/
COPY --link hosts/ hosts/
COPY --link shared/ shared/
COPY --link scripts/ scripts/
COPY --link assets/ assets/
COPY --link templates/ templates/
COPY --link docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd -m -u 1000 kourai && chown -R kourai:kourai /app
USER kourai

EXPOSE ${PORT}

ENTRYPOINT ["/app/entrypoint.sh"]

LABEL org.opencontainers.image.title="Kourai Khryseai — ${HOST_TYPE}" \
    org.opencontainers.image.description="Multi-agent A2A development system — ${PACKAGE_NAME}" \
    org.opencontainers.image.url="https://github.com/ajbarea/kourai_khryseai"
