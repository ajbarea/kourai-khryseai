# Kourai sandbox image — minimal runtime where agent-issued commands execute.
#
# Used by ContainerRunner (shared/src/kourai_common/sandbox.py) when
# KOURAI_SANDBOX=container is set. The player's project worktree is bind-
# mounted at /workspace; commands run there with --network none and capped
# cpu/memory/pids. Network-needing steps (uv pip install, npm install) are
# pre-baked here so the runtime container can stay airgapped.
#
# Build: make sandbox-image     # or `docker build -f docker/sandbox.Dockerfile -t kourai-sandbox:latest .`
#
# research(2026-05): Chainguard wolfi-base over python:3.12-slim — same
# 0-CVE rationale as docker/host.Dockerfile. The Wolfi-bundled npm carries
# its own @xmldom/xmldom 0.8.12 HIGH CVE pair (CVE-2026-41674/41675),
# upstream-blocked until npm pushes a fixed bundle; not exploitable in
# our airgapped sandbox threat model since xmldom only sees npm-internal
# config XML, never agent-controlled input.

ARG PYTHON_VERSION=3.12

FROM cgr.dev/chainguard/wolfi-base:latest

ARG PYTHON_VERSION

USER root

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Tools agents actually invoke: git, ruff, pytest, uv, node. No curl/wget
# — if a hallucinated command tries to fetch payloads, the airgapped
# network kills it before the missing binary matters. uv comes from apk
# (Wolfi keeps it current); ruff + pytest go in via uv pip --system to
# pin them to current PyPI releases.
#
# research(2026-05): nodejs-24 (Active LTS through April 2028) over
# nodejs-22 (Maintenance LTS, EOL April 2027). Node 24 ships npm v11
# (~65% faster installs than v10) and stable native TypeScript
# type-stripping. Wolfi packages both; tracking the current LTS keeps
# the agent sandbox aligned with what new repos pick.
# source: nodejs.org/en/about/previous-releases
RUN --mount=type=cache,target=/var/cache/apk,sharing=locked \
    apk add --no-cache \
        python-${PYTHON_VERSION} \
        py${PYTHON_VERSION}-pip \
        git \
        ca-certificates \
        nodejs-24 \
        npm \
        uv

RUN uv pip install --system --no-cache-dir ruff pytest pytest-asyncio

# Run as a non-root user so a worktree compromise can't escalate inside
# the container even before the bind mount stops it leaving.
RUN adduser -D -h /home/forge -s /bin/sh forge
USER forge

WORKDIR /workspace

# No ENTRYPOINT — ContainerRunner passes the full argv. Default shell so
# `docker run kourai-sandbox` without args lands in a usable prompt during
# manual debugging.
CMD ["/bin/sh"]
