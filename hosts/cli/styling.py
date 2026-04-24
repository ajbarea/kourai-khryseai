"""ANSI color constants — rich gold palette for the Golden Maidens.

True-color goldenrod / gold for brand identity, with fallbacks for
terminals that lack 24-bit color support.
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
