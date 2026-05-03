"""Kallos A2A server — entry point.

Start with: python -m agents.kallos
"""

from __future__ import annotations

import os

from a2a.types import AgentCard, AgentSkill

from agents.kallos.agent_executor import KallosAgentExecutor
from kourai_common.agent_cards import build_card
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT
from kourai_common.log import run_uvicorn, setup_logging
from kourai_common.server import build_a2a_app
from kourai_common.tracing import setup_tracing

AGENT_NAME = "kallos"
log = setup_logging(AGENT_NAME)
PORT = int(os.getenv("PORT", str(AGENT_PORTS[AGENT_NAME])))
HOST = os.getenv("HOST", "0.0.0.0")  # noqa: S104


def build_agent_card() -> AgentCard:
    """Construct the Kallos agent card."""
    skill = AgentSkill(
        id="style_check",
        name="Code Style Check & Cleanup",
        description=(
            "Run linters, fix formatting, clean comments/docstrings "
            "per AJ's style guides. Reports issues and suggested fixes."
        ),
        tags=["linting", "formatting", "style", "cleanup"],
        examples=[
            "clean up comments in src/utils/",
            "run make lint and fix issues",
            "standardize docstrings in the API module",
        ],
    )
    return build_card(
        agent_name=AGENT_NAME,
        display_name="Kallos — Stylist",
        description=(
            "Code style specialist. Runs ruff linter/formatter, analyzes "
            "comments and docstrings, enforces AJ's quality standards. "
            "Auto-fixes issues iteratively via LLM-powered fix loop."
        ),
        skills=[skill],
    )


def main() -> None:
    """Start the Kallos A2A server."""
    setup_tracing(AGENT_NAME, OTEL_ENDPOINT)
    app = build_a2a_app(agent_card=build_agent_card(), executor=KallosAgentExecutor())
    log.info("✨ Kallos starting on %s:%d", HOST, PORT)
    run_uvicorn(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
