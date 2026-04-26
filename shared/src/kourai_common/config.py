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
    "metis": "anthropic/claude-opus-4-6",
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
    "hephaestus": "gemini/gemini-2.0-flash",
    "metis": "gemini/gemini-2.0-flash",
    "techne": "gemini/gemini-2.0-flash",
    "dokimasia": "gemini/gemini-2.0-flash",
    "kallos": "gemini/gemini-2.0-flash",
    "mneme": "gemini/gemini-2.0-flash",
    "puck": "gemini/gemini-2.0-flash",
    "cupid": "gemini/gemini-2.0-flash",
    "aidos": "gemini/gemini-2.0-flash",
    "aletheia": "gemini/gemini-2.0-flash",
}

MODELS_STANDARD_GOOGLE = {
    "hephaestus": "gemini/gemini-2.5-pro",
    "metis": "gemini/gemini-2.5-pro",
    "techne": "gemini/gemini-2.5-pro",
    "dokimasia": "gemini/gemini-2.0-flash",
    "kallos": "gemini/gemini-2.0-flash",
    "mneme": "gemini/gemini-2.0-flash",
    "puck": "gemini/gemini-2.0-flash",
    "cupid": "gemini/gemini-2.0-flash",
    "aidos": "gemini/gemini-2.0-flash",
    "aletheia": "gemini/gemini-2.0-flash",
}

MODELS_SMART_GOOGLE = {
    "hephaestus": "gemini/gemini-2.5-pro",
    "metis": "gemini/gemini-2.5-pro",
    "techne": "gemini/gemini-2.5-pro",
    "dokimasia": "gemini/gemini-2.5-pro",
    "kallos": "gemini/gemini-2.5-pro",
    "mneme": "gemini/gemini-2.5-pro",
    "puck": "gemini/gemini-2.0-flash",
    "cupid": "gemini/gemini-2.5-pro",
    "aidos": "gemini/gemini-2.0-flash",
    "aletheia": "gemini/gemini-2.5-pro",
}

# Local dev models (Ollama) — free, no API key needed
AGENT_MODELS_LOCAL = {
    "hephaestus": "ollama/llama3.3:70b",
    "metis": "ollama/llama3.3:70b",
    "techne": "ollama/llama3.3:70b",
    "dokimasia": "ollama/qwen2.5-coder:32b",
    "kallos": "ollama/llama3.3:8b",
    "mneme": "ollama/llama3.3:8b",
    "puck": "ollama/llama3.3:8b",
    "cupid": "ollama/llama3.3:8b",
    "aidos": "ollama/llama3.3:8b",
    "aletheia": "ollama/llama3.3:70b",
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
