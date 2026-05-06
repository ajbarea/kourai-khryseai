# Kourai Khryseai — Consolidated host Dockerfile (Chainguard Wolfi)
#
# Usage:
#   docker build --build-arg HOST_TYPE=agent --build-arg PACKAGE_NAME=mneme -f docker/host.Dockerfile .
#   docker build --build-arg HOST_TYPE=vn_bridge --build-arg PACKAGE_NAME=vn_bridge -f docker/host.Dockerfile .
#
# research(2026-05): Wolfi over Debian trixie — Chainguard daily-rebuilds
# from upstream sources, sidestepping unfixed HIGH CVEs that Debian's
# security team hasn't backported (nghttp2, libsndfile, glibc per issue
# #98). Verified post-build via `docker scout cves`: 0C 0H 0M 0L vs
# python:3.12-slim's 1H baseline. Wolfi is glibc-based, so PyTorch /
# spaCy / Kokoro manylinux wheels install without the Alpine/musl pain.
# source: edu.chainguard.dev/chainguard/chainguard-images/vuln-comparison/python
#
# research(2026-05): wolfi-base over cgr.dev/chainguard/python — the free
# public-tier python image's :latest-dev tag tracks the newest Python
# (3.14 as of 2026-05) and our pyproject pins requires-python <3.14.
# Pinning to python-3.12 via apk on wolfi-base gives a stable 3.12.x
# without paying for Chainguard's pinned-version tier. Also keeps a
# shell + git + curl at runtime that distroless :latest doesn't ship.
# tradeoff: ~30MB larger than distroless but we already need the shell
# for entrypoint.sh and git for forge agents.

# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.12

# --- Builder ---
FROM cgr.dev/chainguard/wolfi-base:latest AS builder

USER root
WORKDIR /app

ARG PYTHON_VERSION
ARG HOST_TYPE
ARG PACKAGE_NAME

# python-${VERSION}-dev pulls in python-${VERSION} as a dep and adds
# the headers PyAudio (and other C-ext) compiles need. vn_bridge layers
# build-base + portaudio-dev on top for the actual PyAudio compile.
RUN --mount=type=cache,target=/var/cache/apk,sharing=locked \
    apk add --no-cache python-${PYTHON_VERSION}-dev && \
    if [ "${HOST_TYPE}" = "vn_bridge" ]; then \
        apk add --no-cache build-base portaudio-dev; \
    fi

COPY --from=ghcr.io/astral-sh/uv:0.10.10 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON=python${PYTHON_VERSION}

COPY --link pyproject.toml uv.lock ./
COPY --link shared/ shared/
COPY --link scripts/ scripts/
COPY --link agents/ agents/
COPY --link hosts/ hosts/
# kourai-mcp-forge is launched as a stdio subprocess by Techne / Kallos /
# Dokimasia via forge_tool_bridge() (M2 Change 3b/c/d). Installing it
# alongside the per-package install gives the kourai-mcp-forge console
# script to every agent container — cheap (~5MB) and avoids a conditional
# install that branches on PACKAGE_NAME.
COPY --link mcp_servers/ mcp_servers/

RUN uv sync --package kourai-${PACKAGE_NAME} --package kourai-mcp-forge --no-dev --frozen

# --- Runtime ---
FROM cgr.dev/chainguard/wolfi-base:latest AS runtime

USER root
WORKDIR /app

ARG PYTHON_VERSION=3.12
ARG HOST_TYPE
ARG PACKAGE_NAME
ARG PORT=10000

ENV HOST_TYPE=${HOST_TYPE} \
    PACKAGE_NAME=${PACKAGE_NAME} \
    PORT=${PORT} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Runtime sysdeps. python-${VERSION} (without -dev) is enough to run the
# venv copied from the builder. git for project context, curl for the
# healthcheck. vn_bridge adds portaudio so PyAudio can dlopen libportaudio
# at runtime for RealtimeTTS's TextToAudioStream output path.
#
# research(2026-05): espeak-ng is intentionally absent. Wolfi has no
# espeak-ng apk (and no SDL2-image / SDL2-mixer either, but those only
# served the never-deployed gui HOST_TYPE we just dropped). Kokoro's G2P
# dep misaki[en] already pulls espeakng-loader 0.2.4 (manylinux wheel
# bundles libespeak-ng.so + data) plus phonemizer-fork that uses the
# bundled .so via dlopen. Verified in-container: misaki.en.G2P("hello
# world") returns "həlˈO wˈɜɹld" with no /usr/bin/espeak-ng on PATH.
# tradeoff: pinning espeak via uv.lock instead of apk means a wheel
# update risk vs an apk update risk; both are auditable.
# source: github.com/thewh1teagle/espeakng-loader, kokoro 0.9.4 → misaki[en]
RUN --mount=type=cache,target=/var/cache/apk,sharing=locked \
    if [ "${HOST_TYPE}" = "vn_bridge" ]; then \
        apk add --no-cache python-${PYTHON_VERSION} git curl portaudio; \
    else \
        apk add --no-cache python-${PYTHON_VERSION} git curl; \
    fi

# UID 1000 matches host-side bind-mount expectations from M5 plans; the
# git safe.directory wildcard below covers the cross-UID case for now.
RUN adduser -D -u 1000 -h /app kourai

COPY --link --from=builder /app/.venv /app/.venv
# kourai_common.paths.find_project_root() walks up from shared/src/kourai_common/
# looking for the workspace pyproject.toml ([tool.uv.workspace]). It's the
# single source of truth for assets_dir / logs_dir / templates_dir, called at
# module import, so the runtime image must include the workspace pyproject —
# not just the builder stage that uses it for `uv sync`.
COPY --chown=1000:1000 --link pyproject.toml /app/pyproject.toml
COPY --chown=1000:1000 --link agents/ agents/
COPY --chown=1000:1000 --link hosts/ hosts/
COPY --chown=1000:1000 --link shared/ shared/
COPY --chown=1000:1000 --link scripts/ scripts/
COPY --chown=1000:1000 --link mcp_servers/ mcp_servers/
COPY --chown=1000:1000 --link assets/ assets/
COPY --chown=1000:1000 --link templates/ templates/
COPY --chown=1000:1000 --link docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

USER kourai

# Forge worktrees on the host bind-mount are owned by the host user
# (typically UID 1001+ for non-default accounts) while the container runs
# as kourai (UID 1000). Git ≥2.35 refuses to operate on a repo owned by a
# different user without an explicit safe.directory entry (CVE-2022-24765
# hardening). Trust every repo we can see — the bind mount IS the trust
# boundary; if the player has malicious worktrees on disk, the agent
# containers are already compromised. Root-cause UID alignment lives in
# M5 (ROADMAP).
RUN git config --global --add safe.directory '*'

EXPOSE ${PORT}

ENTRYPOINT ["/app/entrypoint.sh"]

LABEL org.opencontainers.image.title="Kourai Khryseai — ${HOST_TYPE}" \
    org.opencontainers.image.description="Multi-agent A2A development system — ${PACKAGE_NAME}" \
    org.opencontainers.image.url="https://github.com/ajbarea/kourai_khryseai" \
    org.opencontainers.image.base.name="cgr.dev/chainguard/wolfi-base:latest"
