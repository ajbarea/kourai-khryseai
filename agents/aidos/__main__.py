"""Aidos A2A server — entry point."""

from __future__ import annotations

import os

import uvicorn
from a2a.types import AgentCard, AgentSkill

from agents.aidos.agent_executor import AidosAgentExecutor
from kourai_common.agent_cards import build_card
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT
from kourai_common.log import setup_logging
from kourai_common.server import build_a2a_app
from kourai_common.tracing import setup_tracing

AGENT_NAME = "aidos"
log = setup_logging(AGENT_NAME)
PORT = int(os.getenv("PORT", str(AGENT_PORTS[AGENT_NAME])))
HOST = os.getenv("HOST", "0.0.0.0")  # noqa: S104


def build_agent_card() -> AgentCard:
    skill = AgentSkill(
        id="slop_detection",
        name="Anti-Slop Language Analysis",
        description=(
            "Scans text for vague marketing jargon ('robust', 'comprehensive', "
            "'leverage') and generates concrete replacements with explanations."
        ),
        tags=["language", "quality", "documentation", "anti-slop"],
        examples=[
            "Review this README for slop",
            "Check my commit message for jargon",
            "Is this docstring too vague?",
        ],
    )
    return build_card(
        agent_name=AGENT_NAME,
        display_name="Aidos — The Shame",
        description=(
            "Anti-slop language enforcer. Removes jargon, marketing speak, and "
            "vague hedges from code, docs, and commit messages. Replaces with "
            "concrete, specific, honest language. Quietly devastating."
        ),
        skills=[skill],
    )


def main() -> None:
    setup_tracing(AGENT_NAME, OTEL_ENDPOINT)
    app = build_a2a_app(agent_card=build_agent_card(), executor=AidosAgentExecutor())
    log.info("🚫 Aidos starting on %s:%d", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
