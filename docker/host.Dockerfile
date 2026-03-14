# Kourai Khryseai — Consolidated host Dockerfile
# Supports: agents (Hephaestus, Metis, Techne, etc.), GUI (Pygame), CLI
# 
# Usage examples:
#   docker build --build-arg HOST_TYPE=agent --build-arg PACKAGE_NAME=mneme -f docker/host.Dockerfile .
#   docker build --build-arg HOST_TYPE=gui --build-arg PACKAGE_NAME=gui -f docker/host.Dockerfile .
#   docker build --build-arg HOST_TYPE=cli --build-arg PACKAGE_NAME=cli -f docker/host.Dockerfile .

# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.12

# ─────────────────────────────────────────────────────────────────────────────
# Builder Stage - Install all dependencies
# ─────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy workspace config + lockfile for reproducible builds
COPY pyproject.toml uv.lock ./
COPY shared/ shared/
COPY scripts/ scripts/

# Build args (used during builder stage)
ARG HOST_TYPE
ARG PACKAGE_NAME

# Copy all source code (agents + hosts directories).
# NOTE: While this copies source for all agents/hosts, only the target package
# (specified by --package argument in uv sync) is installed. The other source code
# is included but not executed. This is a reasonable tradeoff for a single unified
# Dockerfile that builds all host types without conditional logic.
COPY agents/ agents/
COPY hosts/ hosts/

# Install the selected workspace package with uv sync
# Format: kourai-${PACKAGE_NAME} (e.g., kourai-mneme, kourai-gui, kourai-cli)
RUN uv sync --package kourai-${PACKAGE_NAME} --no-dev --frozen

# ─────────────────────────────────────────────────────────────────────────────
# Runtime Stage - Final image with only necessary runtime dependencies
# ─────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS runtime

# Repeated ARGs in runtime stage (ARG scope is per-stage in Docker)
ARG PYTHON_VERSION=3.12
ARG HOST_TYPE
ARG PACKAGE_NAME
ARG PORT=10000

# Set environment variables
ENV HOST_TYPE=${HOST_TYPE}
ENV PACKAGE_NAME=${PACKAGE_NAME}
ENV PORT=${PORT}
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Cross-platform Python symlink
RUN ln -s /usr/local/bin/python3 /usr/local/bin/python || true

# ─────────────────────────────────────────────────────────────────────────────
# Conditional system dependencies based on HOST_TYPE
# ─────────────────────────────────────────────────────────────────────────────

# Agent or CLI: needs git for project context + curl for health checks
RUN if [ "${HOST_TYPE}" = "agent" ] || [ "${HOST_TYPE}" = "cli" ]; then \
    apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*; \
    fi

# GUI: needs SDL2 runtime libraries for pygame (not -dev headers)
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

# ─────────────────────────────────────────────────────────────────────────────
# Copy application code and assets
# ─────────────────────────────────────────────────────────────────────────────

# Copy pre-installed venv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY agents/ agents/
COPY hosts/ hosts/
COPY shared/ shared/
COPY scripts/ scripts/
COPY assets/ assets/

# Put venv on PATH
ENV PATH="/app/.venv/bin:$PATH"

# ─────────────────────────────────────────────────────────────────────────────
# Non-root user for security
# ─────────────────────────────────────────────────────────────────────────────
RUN useradd -m -u 1000 kourai && chown -R kourai:kourai /app
USER kourai

# ─────────────────────────────────────────────────────────────────────────────
# Port
# ─────────────────────────────────────────────────────────────────────────────
EXPOSE ${PORT}

# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint - Adaptive based on HOST_TYPE (CLI vs. GUI vs. Agent)
# ─────────────────────────────────────────────────────────────────────────────

# Agents: python -m agents.${PACKAGE_NAME}
# GUI: python -m hosts.gui
# CLI: python -m hosts.cli

ENTRYPOINT ["sh", "-c", \
    "if [ \"${HOST_TYPE}\" = \"agent\" ]; then python -m agents.${PACKAGE_NAME}; else python -m hosts.${PACKAGE_NAME}; fi" \
    ]

# ─────────────────────────────────────────────────────────────────────────────
# Labels for identification
# ─────────────────────────────────────────────────────────────────────────────
LABEL org.opencontainers.image.title="Kourai Khryseai — ${HOST_TYPE}" \
    org.opencontainers.image.description="Multi-agent A2A development system — ${PACKAGE_NAME}" \
    org.opencontainers.image.url="https://github.com/ajbarea/kourai_khryseai"
