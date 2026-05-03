"""Metis A2A server — entry point.

Start with: python -m agents.metis
"""

from __future__ import annotations

import os

from a2a.types import AgentCard, AgentSkill

from agents.metis.agent_executor import MetisAgentExecutor
from kourai_common.agent_cards import build_card
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT
from kourai_common.log import run_uvicorn, setup_logging
from kourai_common.server import build_a2a_app
from kourai_common.tracing import setup_tracing

AGENT_NAME = "metis"
log = setup_logging(AGENT_NAME)
PORT = int(os.getenv("PORT", str(AGENT_PORTS[AGENT_NAME])))
HOST = os.getenv("HOST", "0.0.0.0")  # noqa: S104


def build_agent_card() -> AgentCard:
    """Construct the Metis agent card."""
    skill = AgentSkill(
        id="create_spec",
        name="Create Implementation Specification",
        description=(
            "Transform rough ideas into detailed requirements with file lists, "
            "acceptance criteria, and implementation steps"
        ),
        tags=["planning", "requirements", "specification"],
        examples=[
            "I want a CSV export button on the dashboard",
            "add authentication to the API",
            "refactor the config loader to use pydantic",
        ],
    )
    return build_card(
        agent_name=AGENT_NAME,
        display_name="Metis — Planner",
        description=(
            "Planning specialist. Transforms rough ideas into structured "
            "implementation specs. Emits machine-readable metadata "
            "for downstream pipeline routing."
        ),
        skills=[skill],
        input_modes=["text", "image"],
    )


def main() -> None:
    """Start the Metis A2A server."""
    setup_tracing(AGENT_NAME, OTEL_ENDPOINT)
    app = build_a2a_app(agent_card=build_agent_card(), executor=MetisAgentExecutor())
    log.info("\U0001f4d0 Metis starting on %s:%d", HOST, PORT)
    run_uvicorn(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
