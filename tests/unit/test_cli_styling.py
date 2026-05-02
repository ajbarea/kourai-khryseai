"""Unit tests for hosts.cli.styling — agent badges + NO_COLOR + truecolor."""

from __future__ import annotations

import importlib
import os
from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def _styling(env: dict[str, str] | None = None):
    """Reload styling under a controlled env so module-level detection runs."""
    full_env = {} if env is None else dict(env)
    with patch.dict(os.environ, full_env, clear=True):
        import hosts.cli.styling as styling

        importlib.reload(styling)
        yield styling


def test_badge_emits_okabe_ito_background_for_known_agent():
    with _styling({"COLORTERM": "truecolor"}) as s:
        out = s.agent_badge("hephaestus")
    # Hephaestus → Okabe-Ito orange #E69F00 = (230, 159, 0)
    assert "\x1b[48;2;230;159;0m" in out
    assert "HEPHAESTUS" in out
    assert out.endswith("\x1b[0m")


def test_badge_uses_distinct_color_per_specialist():
    """Six core specialists each get a distinct hue."""
    with _styling({"COLORTERM": "truecolor"}) as s:
        seen = {
            agent: s.agent_badge(agent)
            for agent in ("hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme")
        }
    # Extract just the bg-color escape from each badge
    bg_codes = {agent: out.split("\x1b[48;2;")[1].split("m")[0] for agent, out in seen.items()}
    assert len(set(bg_codes.values())) == 6, f"Specialists collide on bg color: {bg_codes}"


def test_badge_no_color_env_strips_color_but_keeps_bold():
    """NO_COLOR strips bg+fg but keeps bold per no-color.org spec."""
    with _styling({"NO_COLOR": "1", "COLORTERM": "truecolor"}) as s:
        out = s.agent_badge("hephaestus")
    assert "\x1b[48;2;" not in out  # no bg color
    assert "\x1b[38;2;" not in out  # no fg color
    assert "\x1b[1m" in out  # bold preserved
    assert "HEPHAESTUS" in out


def test_badge_unknown_agent_falls_back_to_plain_bold():
    """Unknown agent name (e.g. vn_bridge) → bold-only, no random color."""
    with _styling({"COLORTERM": "truecolor"}) as s:
        out = s.agent_badge("vn_bridge")
    assert "\x1b[48;2;" not in out  # no bg
    assert "\x1b[1m" in out  # bold
    assert "VN_BRIDGE" in out


def test_badge_no_truecolor_terminal_falls_back_to_plain_bold():
    """Approximating Okabe-Ito into 16-color ANSI would drift the CVD-safe
    property; bold-only is the explicit fallback."""
    with _styling({}) as s:
        out = s.agent_badge("hephaestus")
    assert "\x1b[48;2;" not in out
    assert "\x1b[1m" in out
    assert "HEPHAESTUS" in out


def test_badge_yellow_specialist_gets_black_fg_for_contrast():
    """Yellow #F0E442 needs black-fg; pin the contrast exception."""
    with _styling({"COLORTERM": "truecolor"}) as s:
        out = s.agent_badge("dokimasia")
    assert "\x1b[48;2;240;228;66m" in out  # yellow bg
    assert "\x1b[38;2;0;0;0m" in out  # black fg


def test_comms_window_renders_agent_badge():
    """Integration: comms-window header shows the colored badge."""
    with _styling({"COLORTERM": "truecolor"}) as _:
        import hosts.cli.rendering as rendering

        importlib.reload(rendering)
        out = rendering._comms_window("metis", "test dialogue")
    assert "\x1b[48;2;86;180;233m" in out  # Okabe-Ito sky blue
    assert "METIS" in out


def test_no_color_strips_module_palette_but_keeps_bold_italic_dim():
    """NO_COLOR strips color, keeps bold/italic/dim. Combined codes → bold."""
    with _styling({"NO_COLOR": "1", "COLORTERM": "truecolor"}) as s:
        assert s._GOLD == ""
        assert s._GOLD_BRIGHT == ""
        assert s._GREEN == ""
        assert s._RED == ""
        assert s._GOLD_BOLD == s._BOLD
        assert s._CYAN == s._BOLD
        assert s._BOLD == "\x1b[1m"
        assert s._ITALIC == "\x1b[3m"
        assert s._DIM == "\x1b[2m"
        assert s._RESET == "\x1b[0m"


def test_no_color_unset_keeps_truecolor_palette():
    with _styling({"COLORTERM": "truecolor"}) as s:
        assert "\x1b[38;2;201;148;74m" in s._GOLD
        assert s._RED == "\x1b[0;31m"


def test_badge_padded_with_spaces_so_bg_extends_around_name():
    """Badge visible content is " NAME " — leading/trailing space makes a chip."""
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
