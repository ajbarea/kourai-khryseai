"""Shared agent-card factory for Kourai Khryseai specialists.

Each specialist's ``__main__.py`` builds an ``AgentCard`` advertising its
name, skills, and HTTP URL on the docker-compose network. The ten copies
were 90% identical; this helper is the single source of truth so future
A2A-spec changes (signed cards, extension fields) are a one-file edit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from a2a.types import AgentCapabilities, AgentCard, AgentSkill

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
    """Build the ``AgentCard`` every specialist publishes at startup.

    Args:
        agent_name: Lowercase key used by ``config.AGENT_PORTS`` / ``get_agent_url``.
            Raises ``KeyError`` if unknown.
        display_name: User-facing name (e.g. ``"Kallos — Stylist"``).
        description: Long-form paragraph describing the agent's role.
        skills: Advertised A2A skills.
        version: Semver string; bump in lockstep with the agent's own release.
        input_modes: MIME-ish tags the agent accepts (``text``, ``image``...).
        output_modes: MIME-ish tags the agent emits.
        streaming: Whether the agent streams partial results.
    """
    return AgentCard(
        name=display_name,
        description=description,
        url=get_agent_url(agent_name),
        version=version,
        default_input_modes=list(input_modes),
        default_output_modes=list(output_modes),
        capabilities=AgentCapabilities(streaming=streaming),
        skills=list(skills),
    )
