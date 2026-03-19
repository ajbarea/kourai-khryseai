"""Cupid A2A server — entry point."""

from __future__ import annotations

import os

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agents.cupid.agent_executor import CupidAgentExecutor
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT, get_agent_url
from kourai_common.log import setup_logging
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
    return AgentCard(
        name="Cupid — The Eros",
        description=(
            "Romantic spirit of the forge. Translates maiden emotional subtext, "
            "coaches relationship progression, mediates jealousy, and guides "
            "confession scenes. Arch, witty, and genuinely invested in real connection."
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
        agent_executor=CupidAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )
    log.info("💘 Cupid starting on %s:%d", HOST, PORT)
    uvicorn.run(server.build(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
