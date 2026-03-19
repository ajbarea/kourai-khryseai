"""Puck A2A server — entry point."""

from __future__ import annotations

import os

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agents.puck.agent_executor import PuckAgentExecutor
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT, get_agent_url
from kourai_common.log import setup_logging
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
    return AgentCard(
        name="Puck — The Daimon",
        description=(
            "Pragmatic spirit guide of the forge. Offers hints without spoilers, "
            "nudges players past unproductive patterns, gossips about the maidens, "
            "and hosts jealousy / confession minigames. Irreverent but genuinely caring."
        ),
        url=get_agent_url(AGENT_NAME),
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )


def main() -> None:
    setup_tracing(AGENT_NAME, OTEL_ENDPOINT)
    agent_card = build_agent_card()
    request_handler = DefaultRequestHandler(
        agent_executor=PuckAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )
    log.info("🎭 Puck starting on %s:%d", HOST, PORT)
    uvicorn.run(server.build(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
