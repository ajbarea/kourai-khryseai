"""Techne A2A server — entry point.

Start with: python -m agents.techne
"""

from __future__ import annotations

import os

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, AgentSkill

from agents.techne.agent_executor import TechneAgentExecutor
from kourai_common.agent_cards import build_card
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT
from kourai_common.log import setup_logging
from kourai_common.tracing import setup_tracing

AGENT_NAME = "techne"
log = setup_logging(AGENT_NAME)
PORT = int(os.getenv("PORT", str(AGENT_PORTS[AGENT_NAME])))
HOST = os.getenv("HOST", "0.0.0.0")  # noqa: S104


def build_agent_card() -> AgentCard:
    """Construct the Techne agent card."""
    skill = AgentSkill(
        id="implement_code",
        name="Implement Code Changes",
        description=(
            "Write production code following specs, style guides, and "
            "existing patterns. Reads files before modifying them."
        ),
        tags=["coding", "implementation", "python", "typescript", "react"],
        examples=[
            "implement the CSV export feature per this spec",
            "fix the null pointer in auth.py line 42",
            "add the new API endpoint for /users",
        ],
    )
    return build_card(
        agent_name=AGENT_NAME,
        display_name="Techne — Coder",
        description=(
            "Coding specialist. Reads existing code, generates changes "
            "following AJ's standards, and applies them to disk. "
            "Emits structured artifacts for downstream agents."
        ),
        skills=[skill],
        input_modes=["text", "image"],
    )


def main() -> None:
    """Start the Techne A2A server."""
    setup_tracing(AGENT_NAME, OTEL_ENDPOINT)

    agent_card = build_agent_card()
    request_handler = DefaultRequestHandler(
        agent_executor=TechneAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    log.info("⚙️ Techne starting on %s:%d", HOST, PORT)
    uvicorn.run(server.build(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
