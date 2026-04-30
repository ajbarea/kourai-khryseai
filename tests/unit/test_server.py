"""Unit tests for kourai_common.server.build_a2a_app.

The helper centralizes the A2AStarletteApplication + DefaultRequestHandler +
InMemoryTaskStore boilerplate every agent's __main__ used to spell out by
hand. Each ~10-line copy is now one builder call; the M7 Phase 3 cutover
will flip the helper's implementation rather than every agent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from starlette.applications import Starlette

from kourai_common.server import build_a2a_app

if TYPE_CHECKING:
    from a2a.server.agent_execution import AgentExecutor, RequestContext
    from a2a.server.events import EventQueue


def _stub_executor() -> AgentExecutor:
    """Return a no-op AgentExecutor concrete enough to feed the builder."""
    from a2a.server.agent_execution import AgentExecutor

    class _Stub(AgentExecutor):
        async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
            return None

        async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
            return None

    return _Stub()


def _stub_card() -> AgentCard:
    return AgentCard(
        name="Stub",
        description="Test card.",
        url="http://localhost:9999/",
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="stub",
                name="Stub",
                description="Stub skill.",
                tags=["test"],
                examples=["test"],
            )
        ],
    )


def test_build_a2a_app_returns_starlette_app() -> None:
    app = build_a2a_app(agent_card=_stub_card(), executor=_stub_executor())
    assert isinstance(app, Starlette)


def test_build_a2a_app_mounts_agent_card_route() -> None:
    app = build_a2a_app(agent_card=_stub_card(), executor=_stub_executor())
    paths = [getattr(r, "path", "") for r in app.routes]
    assert any(".well-known/agent-card" in p or "agent-card" in p for p in paths), paths
