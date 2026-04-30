"""Cupid A2A server — entry point."""

from __future__ import annotations

import os

import uvicorn
from a2a.types import AgentCard, AgentSkill

from agents.cupid.agent_executor import CupidAgentExecutor
from kourai_common.agent_cards import build_card
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT
from kourai_common.log import setup_logging
from kourai_common.server import build_a2a_app
from kourai_common.tracing import setup_tracing

AGENT_NAME = "cupid"
log = setup_logging(AGENT_NAME)
PORT = int(os.getenv("PORT", str(AGENT_PORTS[AGENT_NAME])))
HOST = os.getenv("HOST", "0.0.0.0")  # noqa: S104


def build_agent_card() -> AgentCard:
    skill = AgentSkill(
        id="emotional_translation",
        name="Romantic Coaching and Emotional Translation",
        description=(
            "Cupid interprets maiden emotional subtext, coaches relationship "
            "advancement, mediates jealousy events, and guides confession scenes."
        ),
        tags=["romance", "relationship", "emotional", "companion"],
        examples=[
            "What did Kallos actually mean by that?",
            "How do I advance my relationship with Techne?",
            "Help me understand the jealousy situation",
        ],
    )
    return build_card(
        agent_name=AGENT_NAME,
        display_name="Cupid — The Eros",
        description=(
            "Romantic spirit of the forge. Translates maiden emotional subtext, "
            "coaches relationship progression, mediates jealousy, and guides "
            "confession scenes. Arch, witty, and genuinely invested in real connection."
        ),
        skills=[skill],
    )


def main() -> None:
    setup_tracing(AGENT_NAME, OTEL_ENDPOINT)
    app = build_a2a_app(agent_card=build_agent_card(), executor=CupidAgentExecutor())
    log.info("💘 Cupid starting on %s:%d", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
