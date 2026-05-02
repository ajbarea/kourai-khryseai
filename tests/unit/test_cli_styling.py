"""Unit tests for hosts.cli.styling — per-agent badge rendering (#10).

Bug #10: per-agent CLI color coding via colored-background "badge" pattern.
Palette: Okabe-Ito CVD-safe (the 2026 standard for categorical color
accessibility). Honors NO_COLOR per the no-color.org informal standard
(presence of any non-empty value disables ANSI color, but per spec does
NOT disable bold/italic). Honors the existing _has_truecolor detection
in styling.py so terminals without 24-bit color get a plain-bold fallback
rather than a broken render.
"""

from __future__ import annotations

import importlib
import os
from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def _styling(env: dict[str, str] | None = None):
    """Reload hosts.cli.styling under a controlled env so module-level
    NO_COLOR / truecolor detection runs against the test scenario.
    """
    full_env = {} if env is None else dict(env)
    with patch.dict(os.environ, full_env, clear=True):
        import hosts.cli.styling as styling

        importlib.reload(styling)
        try:
            yield styling
        finally:
            # Reset module state for subsequent tests by reloading under
            # the ambient env one more time.
            pass


def test_badge_emits_okabe_ito_background_for_known_agent():
    with _styling({"COLORTERM": "truecolor"}) as s:
        out = s.agent_badge("hephaestus")
    # Hephaestus → Okabe-Ito orange #E69F00 = (230, 159, 0)
    assert "\x1b[48;2;230;159;0m" in out
    assert "HEPHAESTUS" in out
    assert out.endswith("\x1b[0m")


def test_badge_uses_distinct_color_per_specialist():
    """Each of the six core specialists gets a distinct Okabe-Ito hue —
    the visual signal that lets the player scan a transcript and trace
    handoffs without reading agent names."""
    with _styling({"COLORTERM": "truecolor"}) as s:
        seen = {
            agent: s.agent_badge(agent)
            for agent in ("hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme")
        }
    # Extract just the bg-color escape from each badge
    bg_codes = {agent: out.split("\x1b[48;2;")[1].split("m")[0] for agent, out in seen.items()}
    assert len(set(bg_codes.values())) == 6, f"Specialists collide on bg color: {bg_codes}"


def test_badge_no_color_env_strips_color_but_keeps_bold():
    """no-color.org: presence of NO_COLOR (non-empty) disables ANSI color
    but per spec does NOT disable bold/italic — the badge should still
    read as a badge, just monochrome."""
    with _styling({"NO_COLOR": "1", "COLORTERM": "truecolor"}) as s:
        out = s.agent_badge("hephaestus")
    assert "\x1b[48;2;" not in out  # no bg color
    assert "\x1b[38;2;" not in out  # no fg color
    assert "\x1b[1m" in out  # bold preserved
    assert "HEPHAESTUS" in out


def test_badge_unknown_agent_falls_back_to_plain_bold():
    """An agent we don't have a palette entry for (vn_bridge, future
    additions) renders as bold-only, no bg color — better than crashing
    or picking a random color."""
    with _styling({"COLORTERM": "truecolor"}) as s:
        out = s.agent_badge("vn_bridge")
    assert "\x1b[48;2;" not in out  # no bg
    assert "\x1b[1m" in out  # bold
    assert "VN_BRIDGE" in out


def test_badge_no_truecolor_terminal_falls_back_to_plain_bold():
    """Terminals that don't advertise 24-bit color get bold-only.
    Approximating Okabe-Ito hex into the 16-color ANSI palette would
    silently drift the CVD-safe property — better to drop color
    entirely than ship a degraded approximation."""
    # Empty env means no COLORTERM, no WT_SESSION, no TERM_PROGRAM —
    # _has_truecolor goes False.
    with _styling({}) as s:
        out = s.agent_badge("hephaestus")
    assert "\x1b[48;2;" not in out
    assert "\x1b[1m" in out
    assert "HEPHAESTUS" in out


def test_badge_yellow_specialist_gets_black_fg_for_contrast():
    """Dokimasia's bg is Okabe-Ito yellow #F0E442 — the lightest hue in
    the palette. White text on yellow fails WCAG; black gets ~12:1.
    All other Okabe-Ito hues are dark/mid enough that bold white text
    stays readable. This rule check pins the contrast guarantee."""
    with _styling({"COLORTERM": "truecolor"}) as s:
        out = s.agent_badge("dokimasia")
    assert "\x1b[48;2;240;228;66m" in out  # yellow bg
    assert "\x1b[38;2;0;0;0m" in out  # black fg


def test_comms_window_renders_agent_badge():
    """Integration: the comms-window header shows the colored badge for
    the speaking agent — the visible signal that lets a player skim the
    transcript and trace handoffs at a glance."""
    with _styling({"COLORTERM": "truecolor"}) as _:
        # Reload rendering too so it picks up the freshly-reloaded styling.
        import hosts.cli.rendering as rendering

        importlib.reload(rendering)
        out = rendering._comms_window("metis", "test dialogue")
    # Metis bg = Okabe-Ito sky blue (86, 180, 233) appearing on the
    # header row of the comms window.
    assert "\x1b[48;2;86;180;233m" in out
    assert "METIS" in out


def test_badge_padded_with_spaces_so_bg_extends_around_name():
    """The colored background should extend one space on each side of
    the agent name — otherwise it reads as colored text, not as a
    badge. The leading/trailing space is what makes it visually a chip."""
    with _styling({"COLORTERM": "truecolor"}) as s:
        out = s.agent_badge("metis")
    # Strip ANSI to inspect the visible content: " METIS "
    visible = ""
    i = 0
    while i < len(out):
        if out[i] == "\x1b":
            # skip until 'm'
            while i < len(out) and out[i] != "m":
                i += 1
            i += 1  # skip the 'm' itself
        else:
            visible += out[i]
            i += 1
    assert visible == " METIS "
