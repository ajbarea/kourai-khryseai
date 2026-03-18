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
}

MODELS_STANDARD = {
    "hephaestus": "anthropic/claude-sonnet-4-6",
    "metis": "anthropic/claude-sonnet-4-6",
    "techne": "anthropic/claude-sonnet-4-6",
    "dokimasia": "anthropic/claude-haiku-4-5-20251001",
    "kallos": "anthropic/claude-haiku-4-5-20251001",
    "mneme": "anthropic/claude-haiku-4-5-20251001",
}

MODELS_SMART = {
    "hephaestus": "anthropic/claude-sonnet-4-6",
    "metis": "anthropic/claude-opus-4-6",
    "techne": "anthropic/claude-sonnet-4-6",
    "dokimasia": "anthropic/claude-sonnet-4-6",
    "kallos": "anthropic/claude-sonnet-4-6",
    "mneme": "anthropic/claude-sonnet-4-6",
}

# Google Gemini model tiers — mapped to Claude capability equivalents
MODELS_CHEAP_GOOGLE = {
    "hephaestus": "gemini/gemini-2.0-flash",
    "metis": "gemini/gemini-2.0-flash",
    "techne": "gemini/gemini-2.0-flash",
    "dokimasia": "gemini/gemini-2.0-flash",
    "kallos": "gemini/gemini-2.0-flash",
    "mneme": "gemini/gemini-2.0-flash",
}

MODELS_STANDARD_GOOGLE = {
    "hephaestus": "gemini/gemini-2.5-pro",
    "metis": "gemini/gemini-2.5-pro",
    "techne": "gemini/gemini-2.5-pro",
    "dokimasia": "gemini/gemini-2.0-flash",
    "kallos": "gemini/gemini-2.0-flash",
    "mneme": "gemini/gemini-2.0-flash",
}

MODELS_SMART_GOOGLE = {
    "hephaestus": "gemini/gemini-2.5-pro",
    "metis": "gemini/gemini-2.5-pro",
    "techne": "gemini/gemini-2.5-pro",
    "dokimasia": "gemini/gemini-2.5-pro",
    "kallos": "gemini/gemini-2.5-pro",
    "mneme": "gemini/gemini-2.5-pro",
}

# Local dev models (Ollama) — free, no API key needed
AGENT_MODELS_LOCAL = {
    "hephaestus": "ollama/llama3.3:70b",
    "metis": "ollama/llama3.3:70b",
    "techne": "ollama/llama3.3:70b",
    "dokimasia": "ollama/qwen2.5-coder:32b",
    "kallos": "ollama/llama3.3:8b",
    "mneme": "ollama/llama3.3:8b",
}

AGENT_PORTS = {
    "hephaestus": 10000,
    "metis": 10001,
    "techne": 10002,
    "dokimasia": 10003,
    "kallos": 10004,
    "mneme": 10005,
}

# Timeouts per agent (seconds)
AGENT_TIMEOUTS = {
    "agent_card_fetch": 5.0,
    "mneme": 30.0,
    "kallos": 60.0,
    "techne": 120.0,
    "dokimasia": 120.0,
    "metis": 120.0,
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

# When running in Docker, agents talk via service names instead of localhost
DOCKER_MODE = os.getenv("KOURAI_AGENT_HOST", "false").lower() == "true"


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


def get_model(agent_name: str) -> str:
    """Get the LLM model ID for an agent based on the active provider and tier.

    Provider is selected via KOURAI_PROVIDER (anthropic/google/local).
    Tier is selected via KOURAI_MODEL_TIER (cheap/standard/smart).
    """
    if PROVIDER == "local":
        return AGENT_MODELS_LOCAL[agent_name]

    tiers = _PROVIDER_TIERS.get(PROVIDER, _PROVIDER_TIERS["anthropic"])
    models = tiers.get(MODEL_TIER, tiers["cheap"])
    return models[agent_name]


def get_agent_url(agent_name: str) -> str:
    """Get the URL for an agent. Uses Docker service names in container mode."""
    port = AGENT_PORTS[agent_name]
    if DOCKER_MODE:
        return f"http://{agent_name}:{port}/"
    return f"http://127.0.0.1:{port}/"
