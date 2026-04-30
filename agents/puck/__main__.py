"""Puck A2A server — entry point."""

from __future__ import annotations

import os

import uvicorn
from a2a.types import AgentCard, AgentSkill

from agents.puck.agent_executor import PuckAgentExecutor
from kourai_common.agent_cards import build_card
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT
from kourai_common.log import setup_logging
from kourai_common.server import build_a2a_app
from kourai_common.tracing import setup_tracing

AGENT_NAME = "puck"
log = setup_logging(AGENT_NAME)
PORT = int(os.getenv("PORT", str(AGENT_PORTS[AGENT_NAME])))
HOST = os.getenv("HOST", "0.0.0.0")  # noqa: S104


def build_agent_card() -> AgentCard:
    skill = AgentSkill(
        id="guide_and_nudge",
        name="Tutorial Guide and Nudge System",
        description=(
            "Puck guides new players, catches unproductive patterns, brokers "
            "gossip between the maidens, and hosts relationship minigames."
        ),
        tags=["tutorial", "companion", "gossip", "nudge"],
        examples=[
            "I'm confused about how to start",
            "What's Kallos actually like?",
            "Help me understand what just happened",
        ],
    )
    return build_card(
        agent_name=AGENT_NAME,
        display_name="Puck — The Daimon",
        description=(
            "Pragmatic spirit guide of the forge. Offers hints without spoilers, "
            "nudges players past unproductive patterns, gossips about the maidens, "
            "and hosts jealousy / confession minigames. Irreverent but genuinely caring."
        ),
        skills=[skill],
    )


def main() -> None:
    setup_tracing(AGENT_NAME, OTEL_ENDPOINT)
    app = build_a2a_app(agent_card=build_agent_card(), executor=PuckAgentExecutor())
    log.info("🎭 Puck starting on %s:%d", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
