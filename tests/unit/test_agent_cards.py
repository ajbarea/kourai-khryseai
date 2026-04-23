"""Tests for the shared agent-card builder.

Consolidates the ten copies of ``build_agent_card()`` that used to live in
each ``agents/*/__main__.py``. The helper owes callers:

    - the ``url`` must come from ``kourai_common.config.get_agent_url`` so the
      docker-compose network names stay authoritative
    - the v0.3 capability shape (``AgentCapabilities(streaming=True)``) stays
      emitted by default until the v1.0 migration lands
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
    """URL must match ``get_agent_url`` so specialists resolve docker-compose hostnames."""
    from kourai_common.agent_cards import build_card
    from kourai_common.config import get_agent_url

    card = build_card(
        agent_name="kallos",
        display_name="Kallos — Stylist",
        description="Style specialist.",
        skills=[_skill()],
    )
    assert card.url == get_agent_url("kallos")


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
