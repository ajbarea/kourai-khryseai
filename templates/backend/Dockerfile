# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.12

# --- Builder ---
FROM python:${PYTHON_VERSION}-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.10.10 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project

COPY src/ src/
RUN uv sync --no-dev --frozen

# --- Runtime ---
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
