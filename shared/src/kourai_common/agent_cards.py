"""Shared agent-card factory for Kourai Khryseai specialists.

Each specialist's ``__main__.py`` builds an ``AgentCard`` advertising
its name, skills, and HTTP URL on the docker-compose network. This
helper is the single source of truth so spec updates land in one place.

The 1.0 ``AgentCard`` exposes a list of ``supported_interfaces`` rather
than a single top-level ``url``. M7 Phase 6 retired the transitional
v0.3 ``AgentInterface`` entry — every kourai host speaks 1.0 natively.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill

from kourai_common.config import get_agent_url

if TYPE_CHECKING:
    from collections.abc import Sequence


def build_card(
    *,
    agent_name: str,
    display_name: str,
    description: str,
    skills: Sequence[AgentSkill],
    version: str = "0.1.0",
    input_modes: Sequence[str] = ("text",),
    output_modes: Sequence[str] = ("text",),
    streaming: bool = True,
) -> AgentCard:
    """Build the ``AgentCard`` every specialist publishes at startup."""
    url = get_agent_url(agent_name)
    return AgentCard(
        name=display_name,
        description=description,
        version=version,
        default_input_modes=list(input_modes),
        default_output_modes=list(output_modes),
        capabilities=AgentCapabilities(streaming=streaming),
        skills=list(skills),
        supported_interfaces=[
            AgentInterface(
                url=url,
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            ),
        ],
    )
