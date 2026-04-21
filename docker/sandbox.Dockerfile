# Kourai sandbox image — minimal runtime where agent-issued commands execute.
#
# Used by ContainerRunner (shared/src/kourai_common/sandbox.py) when
# KOURAI_SANDBOX=container is set. The player's project worktree is bind-
# mounted at /workspace; commands run there with --network none and capped
# cpu/memory/pids. Network-needing steps (uv pip install, npm install) are
# pre-baked here so the runtime container can stay airgapped.
#
# Build: make sandbox-image     # or `docker build -f docker/sandbox.Dockerfile -t kourai-sandbox:latest .`

FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Tools agents actually invoke: git, ruff, pytest, uv, node. No shells beyond
# /bin/sh. No curl/wget — if a hallucinated command tries to fetch payloads,
# the airgapped network kills it before the missing binary matters.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        git \
        ca-certificates \
        nodejs \
        npm \
 && rm -rf /var/lib/apt/lists/*

# uv (fast Python package manager) and the Python tooling the agents call.
RUN pip install --no-cache-dir uv ruff pytest pytest-asyncio

# Run as a non-root user so a worktree compromise can't escalate inside
# the container even before the bind mount stops it leaving.
RUN useradd --create-home --shell /bin/sh forge
USER forge

WORKDIR /workspace

# No ENTRYPOINT — ContainerRunner passes the full argv. Default shell so
# `docker run kourai-sandbox` without args lands in a usable prompt during
# manual debugging.
CMD ["/bin/sh"]
