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
# kourai-mcp-forge is launched as a stdio subprocess by Techne / Kallos /
# Dokimasia via `forge_tool_bridge()` (M2 Change 3b/c/d). Installing it
# alongside the per-package install gives the `kourai-mcp-forge` console
# script to every agent container — cheap (~5MB) and avoids a conditional
# install that branches on PACKAGE_NAME.
COPY --link mcp_servers/ mcp_servers/

RUN uv sync --package kourai-${PACKAGE_NAME} --package kourai-mcp-forge --no-dev --frozen

# Pre-create non-root user in builder
RUN useradd -m -u 1000 kourai

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

# Agent/CLI/VN bridge: git for project context, curl for health checks
# Agent and VN bridge: espeak-ng for Kokoro TTS runtime support
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    if [ "${HOST_TYPE}" = "agent" ] || [ "${HOST_TYPE}" = "cli" ] || [ "${HOST_TYPE}" = "vn_bridge" ]; then \
    apt-get update && \
    apt-get install -y --no-install-recommends git curl espeak-ng && \
    rm -rf /var/lib/apt/lists/*; \
    fi

# Dokimasia: Chromium + Playwright for E2E frontend testing
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    if [ "${HOST_TYPE}" = "agent" ] && [ "${PACKAGE_NAME}" = "dokimasia" ]; then \
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

# GUI: SDL2 runtime libs for pygame + espeak-ng for Kokoro TTS
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    if [ "${HOST_TYPE}" = "gui" ]; then \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    libsdl2-2.0-0 \
    libsdl2-image-2.0-0 \
    libsdl2-mixer-2.0-0 \
    libsdl2-ttf-2.0-0 \
    libfreetype6 \
    espeak-ng && \
    rm -rf /var/lib/apt/lists/*; \
    fi

# Recreate user in runtime stage
# The second call is fast and idempotent if user already exists
RUN useradd -m -u 1000 kourai 2>/dev/null || true

COPY --link --from=builder /app/.venv /app/.venv
COPY --chown=1000:1000 --link agents/ agents/
COPY --chown=1000:1000 --link hosts/ hosts/
COPY --chown=1000:1000 --link shared/ shared/
COPY --chown=1000:1000 --link scripts/ scripts/
COPY --chown=1000:1000 --link mcp_servers/ mcp_servers/
COPY --chown=1000:1000 --link assets/ assets/
COPY --chown=1000:1000 --link templates/ templates/
COPY --chown=1000:1000 --link docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"

USER kourai

# Forge worktrees on the host bind-mount are owned by the host user (typically
# UID 1001+ for non-default accounts) while the container runs as `kourai`
# (UID 1000). Git ≥2.35 refuses to operate on a repo owned by a different
# user without an explicit safe.directory entry (CVE-2022-24765 hardening).
# Trust every repo we can see — the bind mount IS the trust boundary; if
# the player has malicious worktrees on disk, the agent containers are
# already compromised. Root-cause UID alignment lives in M5 (ROADMAP).
RUN git config --global --add safe.directory '*'

EXPOSE ${PORT}

ENTRYPOINT ["/app/entrypoint.sh"]

LABEL org.opencontainers.image.title="Kourai Khryseai — ${HOST_TYPE}" \
    org.opencontainers.image.description="Multi-agent A2A development system — ${PACKAGE_NAME}" \
    org.opencontainers.image.url="https://github.com/ajbarea/kourai_khryseai"
