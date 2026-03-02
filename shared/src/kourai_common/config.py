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
MAX_ITERATIONS = int(os.getenv("KOURAI_MAX_ITERATIONS", "3"))
STREAM_ENABLED = os.getenv("KOURAI_STREAM_ENABLED", "true").lower() == "true"
USE_LOCAL_MODELS = os.getenv("KOURAI_USE_LOCAL_MODELS", "false").lower() == "true"
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

# When running in Docker, agents talk via service names instead of localhost
DOCKER_MODE = os.getenv("KOURAI_AGENT_HOST", "false").lower() == "true"


def get_model(agent_name: str) -> str:
    """Get the LLM model ID for an agent based on the selected tier."""
    if USE_LOCAL_MODELS:
        return AGENT_MODELS_LOCAL[agent_name]

    tier_map = {"cheap": MODELS_CHEAP, "standard": MODELS_STANDARD, "smart": MODELS_SMART}

    models = tier_map.get(MODEL_TIER, MODELS_CHEAP)
    return models[agent_name]


def get_agent_url(agent_name: str) -> str:
    """Get the URL for an agent. Uses Docker service names in container mode."""
    port = AGENT_PORTS[agent_name]
    if DOCKER_MODE:
        return f"http://{agent_name}:{port}/"
    return f"http://localhost:{port}/"
