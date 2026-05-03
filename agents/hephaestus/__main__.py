"""Hephaestus A2A server — orchestrator entry point.

Start with: python -m agents.hephaestus
"""

from __future__ import annotations

import os

from a2a.types import AgentCard, AgentSkill

from agents.hephaestus.agent_executor import HephaestusAgentExecutor
from kourai_common.agent_cards import build_card
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT
from kourai_common.log import run_uvicorn, setup_logging
from kourai_common.server import build_a2a_app
from kourai_common.tracing import setup_tracing

AGENT_NAME = "hephaestus"
log = setup_logging(AGENT_NAME)
PORT = int(os.getenv("PORT", str(AGENT_PORTS[AGENT_NAME])))
HOST = os.getenv("HOST", "0.0.0.0")  # noqa: S104


def build_agent_card() -> AgentCard:
    """Construct the Hephaestus agent card."""
    route_skill = AgentSkill(
        id="route_request",
        name="Route Development Request",
        description=(
            "Analyze user request and route to the right specialist agents in the correct order"
        ),
        tags=["orchestration", "routing", "pipeline"],
        examples=[
            "implement a CSV export feature",
            "fix the login bug in auth.py",
            "add tests for the payment module",
            "clean up comments in src/utils/",
        ],
    )
    pipeline_skill = AgentSkill(
        id="pipeline_execution",
        name="Execute Development Pipeline",
        description=("Run multi-step workflows: plan -> code -> test -> style -> commit"),
        tags=["pipeline", "workflow", "automation"],
        examples=[
            "full pipeline for feature X",
            "code and test this change",
            "style check and commit prep",
        ],
    )
    chat_skill = AgentSkill(
        id="chat",
        name="Casual Conversation",
        description=(
            "Handle greetings, casual talk, and requests to chat with "
            "specific maidens without requiring a development task"
        ),
        tags=["chat", "conversation", "social"],
        examples=[
            "hey, how's it going?",
            "talk to Kallos",
            "@dokimasia what's up?",
        ],
    )
    return build_card(
        agent_name=AGENT_NAME,
        display_name="Hephaestus — Orchestrator",
        description=(
            "Master orchestrator of Kourai Khryseai. Routes development tasks "
            "to specialist pipelines and handles casual conversation directly. "
            "Emits structured metadata for downstream routing."
        ),
        skills=[route_skill, pipeline_skill, chat_skill],
        input_modes=["text", "image"],
    )


def main() -> None:
    """Start the Hephaestus A2A server."""
    setup_tracing(AGENT_NAME, OTEL_ENDPOINT)
    app = build_a2a_app(agent_card=build_agent_card(), executor=HephaestusAgentExecutor())
    log.info("\U0001f525 Hephaestus starting on %s:%d", HOST, PORT)
    run_uvicorn(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
