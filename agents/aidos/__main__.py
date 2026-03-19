"""Aidos A2A server — entry point."""

from __future__ import annotations

import os

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agents.aidos.agent_executor import AidosAgentExecutor
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT, get_agent_url
from kourai_common.log import setup_logging
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
    return AgentCard(
        name="Aidos — The Shame",
        description=(
            "Anti-slop language enforcer. Removes jargon, marketing speak, and "
            "vague hedges from code, docs, and commit messages. Replaces with "
            "concrete, specific, honest language. Quietly devastating."
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
        agent_executor=AidosAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )
    log.info("🚫 Aidos starting on %s:%d", HOST, PORT)
    uvicorn.run(server.build(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
