"""Tests for the shared agent-card builder.

Consolidates the ten copies of ``build_agent_card()`` that used to live in
each ``agents/*/__main__.py``. The helper owes callers:

    - the URL on every ``supported_interfaces`` entry comes from
      ``kourai_common.config.get_agent_url`` so docker-compose hostnames
      stay authoritative
    - the 1.0 wire shape — ``AgentCard.supported_interfaces`` advertising
      both 1.0 and 0.3 protocol versions while M7 Phase 6 is pending —
      stays emitted by default
"""

from __future__ import annotations

import pytest
from a2a.types import AgentSkill


def _skill() -> AgentSkill:
    return AgentSkill(
        id="sample",
        name="Sample",
        description="desc",
        tags=["t"],
        examples=["do a thing"],
    )


def test_build_card_sets_core_fields() -> None:
    from kourai_common.agent_cards import build_card

    card = build_card(
        agent_name="hephaestus",
        display_name="Hephaestus — Orchestrator",
        description="Routes requests.",
        skills=[_skill()],
    )
    assert card.name == "Hephaestus — Orchestrator"
    assert card.description == "Routes requests."
    assert card.version == "0.1.0"
    assert card.default_input_modes == ["text"]
    assert card.default_output_modes == ["text"]
    assert len(card.skills) == 1


def test_build_card_url_comes_from_config() -> None:
    """Every supported_interfaces URL must match ``get_agent_url``."""
    from kourai_common.agent_cards import build_card
    from kourai_common.config import get_agent_url

    card = build_card(
        agent_name="kallos",
        display_name="Kallos — Stylist",
        description="Style specialist.",
        skills=[_skill()],
    )
    expected = get_agent_url("kallos")
    assert card.supported_interfaces, "card must advertise at least one interface"
    for interface in card.supported_interfaces:
        assert interface.url == expected


def test_build_card_advertises_1_0_and_0_3_interfaces() -> None:
    """Transitional safety net — Phase 6 retires the 0.3 fallback entry."""
    from kourai_common.agent_cards import build_card

    card = build_card(
        agent_name="kallos",
        display_name="Kallos",
        description="x",
        skills=[_skill()],
    )
    versions = sorted(iface.protocol_version for iface in card.supported_interfaces)
    assert versions == ["0.3", "1.0"]


def test_build_card_default_streaming_capability() -> None:
    from kourai_common.agent_cards import build_card

    card = build_card(
        agent_name="metis",
        display_name="Metis — Planner",
        description="Plans tasks.",
        skills=[_skill()],
    )
    assert card.capabilities.streaming is True


def test_build_card_accepts_image_input_mode() -> None:
    """Hephaestus accepts image uploads; the helper must not lock input modes to text-only."""
    from kourai_common.agent_cards import build_card

    card = build_card(
        agent_name="hephaestus",
        display_name="Hephaestus — Orchestrator",
        description="Routes.",
        skills=[_skill()],
        input_modes=["text", "image"],
    )
    assert card.default_input_modes == ["text", "image"]


def test_build_card_rejects_unknown_agent_name() -> None:
    """Typos in the agent name must fail loudly rather than emit a card with a
    broken URL — the docker-compose network is the source of truth."""
    from kourai_common.agent_cards import build_card

    with pytest.raises(KeyError):
        build_card(
            agent_name="not-a-real-agent",
            display_name="Nobody",
            description="x",
            skills=[_skill()],
        )
