"""Unit tests for canonical per-agent colors on ``AGENT_METADATA``.

Adds ``hex_color`` and ``rgb`` keys for all 8 agents so the VN's
``script_data.rpy:49-56`` lookup pattern stops being a latent KeyError
on startup, and the GUI's local ``_AGENT_COLORS`` table can derive from
shared rather than duplicate it.

Color sourcing rationale (also documented at the constants):
  * 6 main maidens (hephaestus / metis / techne / dokimasia / kallos /
    mneme) — keep the GUI's deliberate warm-gold theme palette. Not
    "arbitrary picks": each is narrative-fitting (forge gold, gold-ivory,
    amber, crimson, rose-gold, mystic purple-gold).
  * puck + cupid — Okabe-Ito CVD-safe values from ``hosts/cli/styling.py``
    (the only host that ever defined them); matches the project's
    stated "Okabe-Ito over arbitrary picks" preference for
    secondary-roster agents that don't have a thematic gold variant.
"""

from __future__ import annotations

import pytest

from kourai_common.agents import AGENT_METADATA

_ALL_AGENTS = ("hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme", "puck", "cupid")


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_every_agent_has_hex_color(name: str):
    meta = AGENT_METADATA[name]
    color = meta.get("hex_color")
    assert isinstance(color, str), f"{name} missing hex_color"
    assert color.startswith("#"), f"{name} hex_color {color!r} not '#RRGGBB' shape"
    assert len(color) == 7, f"{name} hex_color {color!r} not exactly '#RRGGBB'"


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_every_agent_has_rgb_tuple(name: str):
    meta = AGENT_METADATA[name]
    rgb = meta.get("rgb")
    assert isinstance(rgb, tuple), f"{name} missing rgb tuple"
    assert len(rgb) == 3, f"{name} rgb has {len(rgb)} components, want 3"
    for channel in rgb:
        assert isinstance(channel, int)
        assert 0 <= channel <= 255


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_hex_color_matches_rgb(name: str):
    """``hex_color`` is the lowercase #RRGGBB form of ``rgb`` — no drift."""
    meta = AGENT_METADATA[name]
    rgb = meta["rgb"]
    expected = "#{:02X}{:02X}{:02X}".format(*rgb)  # type: ignore[misc]
    assert meta["hex_color"].upper() == expected, (
        f"{name}: hex_color {meta['hex_color']!r} doesn't match rgb {rgb!r}"
    )


def test_puck_and_cupid_use_okabe_ito_values():
    # puck and cupid are the secondary-roster agents the GUI's gold theme
    # doesn't cover; CLI styling.py shipped Okabe-Ito values for them.
    # Lock in those exact values so a future "let's pick a vibe" PR has
    # to consciously override the CVD-safe palette in code review.
    assert AGENT_METADATA["puck"]["hex_color"] == "#009E73"  # Okabe-Ito bluish green
    assert AGENT_METADATA["cupid"]["hex_color"] == "#D55E00"  # Okabe-Ito vermillion


def test_six_main_maidens_keep_gui_gold_palette():
    # Lock the warm-gold theme so a future "DRY all colors to Okabe-Ito"
    # walk-back has to be a deliberate code-review decision, not silent.
    expected = {
        "hephaestus": "#DA8C20",
        "metis": "#C8B464",
        "techne": "#FFC832",
        "dokimasia": "#DA5032",
        "kallos": "#FFDCA0",
        "mneme": "#B496DC",
    }
    for name, hex_value in expected.items():
        assert AGENT_METADATA[name]["hex_color"] == hex_value, (
            f"{name} canonical color drifted from {hex_value!r}"
        )
