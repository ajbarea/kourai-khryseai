# syntax=docker/dockerfile:1
#
# Reference template: Techne reads this when scaffolding a backend project for
# the player. Whatever shape lives here propagates into every generated repo,
# so the base-image choice is a player-facing security default.
#
# research(2026-05): Chainguard Wolfi over python:3.12-slim — same rationale as
# kourai's own infra migration (#98 / #125). Wolfi is daily-rebuilt from
# upstream sources, sidestepping unfixed Debian-glibc HIGH CVEs (CVE-2026-5435
# and friends). Glibc-based, so the FastAPI / SQLAlchemy / asyncpg manylinux
# wheels install without Alpine/musl pain. apk-pinned python-3.12 keeps us on
# a stable 3.12.x while the public-tier chainguard/python:latest-dev tracks
# 3.14.
# source: docker/host.Dockerfile in this repo, edu.chainguard.dev vuln-comparison

ARG PYTHON_VERSION=3.12

# --- Builder ---
FROM cgr.dev/chainguard/wolfi-base:latest AS builder

USER root
WORKDIR /app

ARG PYTHON_VERSION

RUN --mount=type=cache,target=/var/cache/apk,sharing=locked \
    apk add --no-cache python-${PYTHON_VERSION}-dev

COPY --from=ghcr.io/astral-sh/uv:0.10.10 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON=python${PYTHON_VERSION}

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project

COPY src/ src/
RUN uv sync --no-dev --frozen

# --- Runtime ---
FROM cgr.dev/chainguard/wolfi-base:latest AS runtime

USER root
WORKDIR /app

ARG PYTHON_VERSION=3.12

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# asyncpg speaks the PostgreSQL wire protocol directly; no libpq needed.
RUN --mount=type=cache,target=/var/cache/apk,sharing=locked \
    apk add --no-cache python-${PYTHON_VERSION}

RUN adduser -D -u 1000 -h /app app

COPY --from=builder --chown=1000:1000 /app/.venv /app/.venv
COPY --chown=1000:1000 src/ src/
COPY --chown=1000:1000 alembic/ alembic/
COPY --chown=1000:1000 alembic.ini .

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
