"""ANSI color constants — gold palette + Okabe-Ito CVD-safe agent badges.

Truecolor by default, with NO_COLOR + 16-color terminal fallbacks that
strip color but preserve bold/italic/dim per the no-color.org spec.
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

_no_color = bool(os.environ.get("NO_COLOR", ""))

# COLORTERM is the canonical signal but few terminals set it; also accept
# well-known emulator env vars and any 256color TERM.
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

# NO_COLOR overrides truecolor + 16-color: strip color, keep bold/dim/italic.
if _no_color:
    _GOLD = ""
    _GOLD_BRIGHT = ""
    _GOLD_BOLD = _BOLD
    _CYAN = _BOLD
    _GREEN = ""
    _RED = ""


# Specialists each get a distinct Okabe-Ito hue; companions/support land
# on neutral gray or share with a thematic sibling.
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

# Yellow #F0E442 fails contrast against bold white (~2:1); pin black-fg
# exception explicitly. Every other Okabe-Ito hue is dark enough for white.
_BLACK_FG_BG_RGB = frozenset({(240, 228, 66)})


def agent_badge(name: str) -> str:
    """Render `name` as a colored-bg chip: " NAME " bold, Okabe-Ito hue.

    Falls back to bold-only when NO_COLOR is set, the terminal lacks
    truecolor, or `name` isn't in the palette.
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
