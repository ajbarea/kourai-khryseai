"""Static fallback agent cards for discovery-without-live-connect.

When Hephaestus boots and a specialist hasn't come up yet,
``A2ACardResolver.get_agent_card()`` times out and the whole orchestrator
stalls on cold start. The fallback below synthesizes a minimal AgentCard
from the agent name + URL so the client can still be constructed; the
next send attempt drives a real card fetch naturally.

Aligned with the 2026 MCP roadmap's discovery-without-connect priority
(``.well-known`` metadata). Rich cards continue to live with each
specialist's ``__main__.py`` — keep those authoritative.
"""

from __future__ import annotations

from a2a.types import AgentCapabilities, AgentCard, AgentInterface


def fallback_card_for(agent_name: str, agent_url: str) -> AgentCard:
    """Build the minimal card used when live discovery fails.

    Records that this is a fallback in ``version`` so traces/logs can
    tell a fresh-booted cold connection apart from a live-discovered one.
    Advertises both 1.0 and 0.3 protocol versions while M7 Phase 6 is
    pending — see ``agent_cards.build_card`` for the same shape on the
    rich-card path.
    """
    return AgentCard(
        name=agent_name,
        description=f"[manifest fallback] {agent_name} at {agent_url}",
        version="0.0.0-fallback",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[],
        supported_interfaces=[
            AgentInterface(
                url=agent_url,
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            ),
            AgentInterface(
                url=agent_url,
                protocol_binding="JSONRPC",
                protocol_version="0.3",
            ),
        ],
    )
