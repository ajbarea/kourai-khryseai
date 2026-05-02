"""ANSI color constants — rich gold palette for the Golden Maidens.

True-color goldenrod / gold for brand identity, with fallbacks for
terminals that lack 24-bit color support.

Per-agent badges (#10) use the Okabe-Ito CVD-safe palette — the 2026
standard for categorical accessibility. NO_COLOR (no-color.org) and
the ambient _has_truecolor signal both gate the colored render, with
plain-bold fallback. Approximating Okabe-Ito into 16-color ANSI is
deliberately NOT attempted — silent CVD-safety drift is worse than
no color at all.
"""

from __future__ import annotations

import os

# True-color warm amber gold — matches docs/stylesheets/variables.css tiers
# (gold-light #F1D2A1, gold-mid #C9944A, gold-dark #AA771C) so CLI, GUI,
# docs site, and poster all share one palette.
_GOLD = "\033[38;2;201;148;74m"  # #C9944A — warm amber (gold-mid)
_GOLD_BRIGHT = "\033[38;2;241;210;161m"  # #F1D2A1 — champagne (gold-light)
_GOLD_BOLD = "\033[1;38;2;201;148;74m"  # bold warm amber
_CYAN = "\033[1;36m"
_GREEN = "\033[38;2;144;238;144m"  # light green
_RED = "\033[0;31m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_ITALIC = "\033[3m"
_RESET = "\033[0m"

# NO_COLOR (no-color.org informal standard, 2018, broadly adopted by 2026):
# any non-empty value disables ANSI color output. Per spec, this only
# affects color — bold/underline/italic stay on so structural emphasis
# still reads as emphasis.
_no_color = bool(os.environ.get("NO_COLOR", ""))

# Fallback for terminals without true-color. COLORTERM is the canonical
# signal but most terminals don't set it (WSL, Windows Terminal, macOS
# Terminal, VSCode, etc. all support 24-bit color without it), so also
# accept well-known emulator env vars and any TERM that advertises 256
# colors — modern 256-color terminals effectively all honor \033[38;2;…m.
_has_truecolor = bool(
    os.environ.get("COLORTERM", "") in ("truecolor", "24bit")
    or os.environ.get("WT_SESSION", "")  # Windows Terminal
    or os.environ.get("TERM_PROGRAM", "")
    in ("vscode", "iTerm.app", "WezTerm", "Apple_Terminal", "Hyper")
    or "256color" in os.environ.get("TERM", "")
)
if not _has_truecolor:
    _GOLD = "\033[1;33m"
    _GOLD_BRIGHT = "\033[1;93m"
    _GOLD_BOLD = "\033[1;33m"
    _GREEN = "\033[1;32m"


# ---------------------------------------------------------------------------
# Per-agent badge palette — Okabe-Ito CVD-safe (#10)
# ---------------------------------------------------------------------------
# Mapping from agent name to background RGB. The eight Okabe-Ito hues are
# the canonical CVD-safe palette for categorical data; #999999 is the
# common 9th "neutral" addition for support-role agents that don't carry
# a primary identity. Specialists each get a distinct hue so handoffs
# read at a glance; companions/support land on shared or neutral entries.
_AGENT_BADGE_COLORS: dict[str, tuple[int, int, int]] = {
    "hephaestus": (230, 159, 0),  # #E69F00 orange — forge fire
    "metis": (86, 180, 233),  # #56B4E9 sky blue — analytical mind
    "techne": (0, 158, 115),  # #009E73 bluish green — code & growth
    "dokimasia": (240, 228, 66),  # #F0E442 yellow — scrutiny / test alert
    "kallos": (0, 114, 178),  # #0072B2 blue — formal refinement
    "mneme": (204, 121, 167),  # #CC79A7 reddish purple — mystic memory
    "cupid": (213, 94, 0),  # #D55E00 vermillion — heart
    "puck": (0, 158, 115),  # green (shared with techne — both makers)
    "aletheia": (153, 153, 153),  # #999999 gray — neutral truth
    "aidos": (153, 153, 153),  # gray — neutral respect
}

# Yellow Okabe-Ito #F0E442 is too light for bold-white text (~2:1
# contrast); black-on-yellow gets ~12:1. Every other Okabe-Ito hue + the
# neutral gray have enough darkness that bold white reads cleanly. Pin
# the exception explicitly so the contrast guarantee is auditable.
_BLACK_FG_BG_RGB = frozenset({(240, 228, 66)})


def agent_badge(name: str) -> str:
    """Render an agent name as an Okabe-Ito-colored background "badge".

    Examples:
        agent_badge("hephaestus")  # → " HEPHAESTUS " on orange bg, bold white fg
        NO_COLOR=1 agent_badge(...) → " HEPHAESTUS " bold-only, no color
        agent_badge("vn_bridge")  # unknown → bold-only fallback

    The leading/trailing space is what makes the colored region read as
    a discrete chip rather than colored text. Always uppercase, always
    bold — even in the no-color paths — so the structural emphasis
    survives palette stripping.
    """
    label = f" {name.upper()} "
    if _no_color or not _has_truecolor:
        return f"{_BOLD}{label}{_RESET}"

    rgb = _AGENT_BADGE_COLORS.get(name)
    if rgb is None:
        return f"{_BOLD}{label}{_RESET}"

    r, g, b = rgb
    fg_r, fg_g, fg_b = (0, 0, 0) if rgb in _BLACK_FG_BG_RGB else (255, 255, 255)
    return f"\033[1m\033[38;2;{fg_r};{fg_g};{fg_b}m\033[48;2;{r};{g};{b}m{label}{_RESET}"
