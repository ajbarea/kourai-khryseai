"""Aletheia A2A server — entry point."""

from __future__ import annotations

import os

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, AgentSkill

from agents.aletheia.agent_executor import AletheiaAgentExecutor
from kourai_common.agent_cards import build_card
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT
from kourai_common.log import setup_logging
from kourai_common.tracing import setup_tracing

AGENT_NAME = "aletheia"
log = setup_logging(AGENT_NAME)
PORT = int(os.getenv("PORT", str(AGENT_PORTS[AGENT_NAME])))
HOST = os.getenv("HOST", "0.0.0.0")  # noqa: S104


def build_agent_card() -> AgentCard:
    skill = AgentSkill(
        id="research_validation",
        name="Research Citation Validation",
        description=(
            "Validates that technical claims have citations, verifies 'Research:' "
            "comment format, and flags unsubstantiated algorithmic choices."
        ),
        tags=["research", "citations", "validation", "quality"],
        examples=[
            "Validate citations in this file",
            "Check if these algorithmic claims are supported",
            "Verify the research references in this docstring",
        ],
    )
    return build_card(
        agent_name=AGENT_NAME,
        display_name="Aletheia — The Truth",
        description=(
            "Research validator and citation enforcer. Finds unsubstantiated "
            "algorithmic claims, verifies Research: comment formats, and flags "
            "vague 'industry standard' references. Never fabricates citations. "
            "Serene, thorough, and gently implacable."
        ),
        skills=[skill],
    )


def main() -> None:
    setup_tracing(AGENT_NAME, OTEL_ENDPOINT)
    agent_card = build_agent_card()
    request_handler = DefaultRequestHandler(
        agent_executor=AletheiaAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )
    log.info("🔬 Aletheia starting on %s:%d", HOST, PORT)
    uvicorn.run(server.build(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
