"""Shared configuration for all Kourai Khryseai agents."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# Model Tier Definitions — LiteLLM provider prefixes
MODELS_CHEAP = {
    "hephaestus": "anthropic/claude-haiku-4-5-20251001",
    "metis": "anthropic/claude-haiku-4-5-20251001",
    "techne": "anthropic/claude-haiku-4-5-20251001",
    "dokimasia": "anthropic/claude-haiku-4-5-20251001",
    "kallos": "anthropic/claude-haiku-4-5-20251001",
    "mneme": "anthropic/claude-haiku-4-5-20251001",
    "puck": "anthropic/claude-haiku-4-5-20251001",
    "cupid": "anthropic/claude-haiku-4-5-20251001",
    "aidos": "anthropic/claude-haiku-4-5-20251001",
    "aletheia": "anthropic/claude-haiku-4-5-20251001",
}

MODELS_STANDARD = {
    "hephaestus": "anthropic/claude-sonnet-4-6",
    "metis": "anthropic/claude-sonnet-4-6",
    "techne": "anthropic/claude-sonnet-4-6",
    "dokimasia": "anthropic/claude-haiku-4-5-20251001",
    "kallos": "anthropic/claude-haiku-4-5-20251001",
    "mneme": "anthropic/claude-haiku-4-5-20251001",
    "puck": "anthropic/claude-haiku-4-5-20251001",
    "cupid": "anthropic/claude-haiku-4-5-20251001",
    "aidos": "anthropic/claude-haiku-4-5-20251001",
    "aletheia": "anthropic/claude-sonnet-4-6",
}

MODELS_SMART = {
    "hephaestus": "anthropic/claude-sonnet-4-6",
    "metis": "anthropic/claude-opus-4-7",
    "techne": "anthropic/claude-sonnet-4-6",
    "dokimasia": "anthropic/claude-sonnet-4-6",
    "kallos": "anthropic/claude-sonnet-4-6",
    "mneme": "anthropic/claude-sonnet-4-6",
    "puck": "anthropic/claude-haiku-4-5-20251001",
    "cupid": "anthropic/claude-sonnet-4-6",
    "aidos": "anthropic/claude-haiku-4-5-20251001",
    "aletheia": "anthropic/claude-sonnet-4-6",
}

# Google Gemini model tiers — mapped to Claude capability equivalents
MODELS_CHEAP_GOOGLE = {
    "hephaestus": "gemini/gemini-2.5-flash-lite",
    "metis": "gemini/gemini-2.5-flash-lite",
    "techne": "gemini/gemini-2.5-flash-lite",
    "dokimasia": "gemini/gemini-2.5-flash-lite",
    "kallos": "gemini/gemini-2.5-flash-lite",
    "mneme": "gemini/gemini-2.5-flash-lite",
    "puck": "gemini/gemini-2.5-flash-lite",
    "cupid": "gemini/gemini-2.5-flash-lite",
    "aidos": "gemini/gemini-2.5-flash-lite",
    "aletheia": "gemini/gemini-2.5-flash-lite",
}

MODELS_STANDARD_GOOGLE = {
    "hephaestus": "gemini/gemini-2.5-pro",
    "metis": "gemini/gemini-2.5-pro",
    "techne": "gemini/gemini-2.5-pro",
    "dokimasia": "gemini/gemini-2.5-flash-lite",
    "kallos": "gemini/gemini-2.5-flash-lite",
    "mneme": "gemini/gemini-2.5-flash-lite",
    "puck": "gemini/gemini-2.5-flash-lite",
    "cupid": "gemini/gemini-2.5-flash-lite",
    "aidos": "gemini/gemini-2.5-flash-lite",
    "aletheia": "gemini/gemini-2.5-flash-lite",
}

MODELS_SMART_GOOGLE = {
    "hephaestus": "gemini/gemini-2.5-pro",
    "metis": "gemini/gemini-2.5-pro",
    "techne": "gemini/gemini-2.5-pro",
    "dokimasia": "gemini/gemini-2.5-pro",
    "kallos": "gemini/gemini-2.5-pro",
    "mneme": "gemini/gemini-2.5-pro",
    "puck": "gemini/gemini-2.5-flash-lite",
    "cupid": "gemini/gemini-2.5-pro",
    "aidos": "gemini/gemini-2.5-flash-lite",
    "aletheia": "gemini/gemini-2.5-pro",
}

# Local dev models (Ollama) — free, no API key needed.
# Sized for a single consumer GPU: 7-8B for the reasoning agents, 3B for the
# light ones. Tags are exact — Ollama treats `llama3.1:8b` and
# `llama3.1:8b-instruct-q4_K_M` as different models, so these must match what
# `ollama pull` fetched. See docs/configuration.md for the pull commands.
AGENT_MODELS_LOCAL = {
    "hephaestus": "ollama/llama3.1:8b-instruct-q4_K_M",
    "metis": "ollama/qwen2.5:7b-instruct",
    "techne": "ollama/qwen2.5:7b-instruct",
    "dokimasia": "ollama/qwen2.5:7b-instruct",
    "kallos": "ollama/llama3.2:3b-instruct-q4_K_M",
    "mneme": "ollama/llama3.2:3b-instruct-q4_K_M",
    "puck": "ollama/qwen2.5:3b-instruct",
    "cupid": "ollama/llama3.1:8b-instruct-q4_K_M",
    "aidos": "ollama/qwen2.5:3b-instruct",
    "aletheia": "ollama/llama3.1:8b-instruct-q4_K_M",
}

AGENT_PORTS = {
    "hephaestus": 10000,
    "metis": 10001,
    "techne": 10002,
    "dokimasia": 10003,
    "kallos": 10004,
    "mneme": 10005,
    "puck": 10006,
    "cupid": 10007,
    "aidos": 10008,
    "aletheia": 10009,
}

# Timeouts per agent (seconds)
AGENT_TIMEOUTS = {
    "agent_card_fetch": 5.0,
    "mneme": 30.0,
    "kallos": 60.0,
    "techne": 120.0,
    "dokimasia": 120.0,
    "metis": 120.0,
    "puck": 30.0,
    "cupid": 60.0,
    "aidos": 60.0,
    "aletheia": 120.0,
    "hephaestus_pipeline": 600.0,
}

# Environment config
LOG_LEVEL = os.getenv("KOURAI_LOG_LEVEL", "INFO")
MODEL_TIER = os.getenv("KOURAI_MODEL_TIER", "cheap").lower()
MAX_ITERATIONS = int(os.getenv("KOURAI_MAX_ITERATIONS", "5"))
STREAM_ENABLED = os.getenv("KOURAI_STREAM_ENABLED", "true").lower() == "true"
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

# Provider selection: "anthropic" (default), "google", or "local"
PROVIDER = os.getenv("KOURAI_PROVIDER", "anthropic").lower()


_PROVIDER_TIERS: dict[str, dict[str, dict[str, str]]] = {
    "anthropic": {
        "cheap": MODELS_CHEAP,
        "standard": MODELS_STANDARD,
        "smart": MODELS_SMART,
    },
    "google": {
        "cheap": MODELS_CHEAP_GOOGLE,
        "standard": MODELS_STANDARD_GOOGLE,
        "smart": MODELS_SMART_GOOGLE,
    },
}


TIER_NAMES: tuple[str, ...] = ("cheap", "standard", "smart")


def get_tier() -> str:
    """Read the active tier. Use this from CLI/GUI code instead of
    ``from kourai_common.config import MODEL_TIER`` — the bare import
    caches the value and won't see ``set_tier`` mutations.
    """
    return MODEL_TIER


def set_tier(tier: str) -> None:
    """Mutate the process-wide ``MODEL_TIER`` so subsequent ``get_model``
    calls resolve to the new tier without a process restart.

    Used by the CLI ``/model <tier>`` slash command. Raises ``ValueError``
    on unknown tier name rather than silently falling back — the slash
    command surface is the validation boundary.
    """
    normalized = tier.strip().lower()
    if normalized not in TIER_NAMES:
        raise ValueError(f"unknown tier {tier!r}; expected one of {TIER_NAMES}")
    global MODEL_TIER
    MODEL_TIER = normalized


def get_model(agent_name: str, tier: str | None = None) -> str:
    """Get the LLM model ID for an agent based on the active provider and tier.

    Provider is selected via KOURAI_PROVIDER (anthropic/google/local).
    Tier defaults to KOURAI_MODEL_TIER (cheap/standard/smart). Pass
    ``tier`` to override per-call — useful when an agent's quick
    auxiliary call (e.g., Metis's M14 ``discuss_tradeoffs``) should
    run at a cheaper tier than the active pipeline.
    Set KOURAI_MODEL_OVERRIDE to force a specific model for all agents
    (useful in test environments with a mock LLM proxy).
    """
    override = os.getenv("KOURAI_MODEL_OVERRIDE")
    if override:
        return override

    if PROVIDER == "local":
        return AGENT_MODELS_LOCAL[agent_name]

    effective_tier = tier or MODEL_TIER
    tiers = _PROVIDER_TIERS.get(PROVIDER, _PROVIDER_TIERS["anthropic"])
    models = tiers.get(effective_tier, tiers["cheap"])
    return models[agent_name]


def get_agent_url(agent_name: str) -> str:
    """Get the URL for an agent. Uses Docker service names."""
    port = AGENT_PORTS[agent_name]
    return f"http://{agent_name}:{port}/"


def get_host_agent_url(agent_name: str) -> str:
    """Get the host-reachable URL for an agent (CLI/GUI clients).

    Docker service names like ``http://hephaestus:10000/`` only resolve from
    inside the docker-compose network. Host-side clients reach agents through
    the published port on ``localhost``. ``make cli`` paves over this by
    passing ``--agent http://localhost:10000/`` explicitly; this helper makes
    direct ``python -m hosts.cli`` / ``python -m hosts.gui`` invocations work
    too.
    """
    port = AGENT_PORTS[agent_name]
    return f"http://localhost:{port}/"
