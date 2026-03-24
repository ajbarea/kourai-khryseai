"""ANSI color constants — rich gold palette for the Golden Maidens.

True-color goldenrod / gold for brand identity, with fallbacks for
terminals that lack 24-bit color support.
"""

from __future__ import annotations

import os

# True-color goldenrod / gold for brand identity
_GOLD = "\033[38;2;218;165;32m"  # goldenrod
_GOLD_BRIGHT = "\033[38;2;255;215;0m"  # pure gold
_GOLD_BOLD = "\033[1;38;2;218;165;32m"  # bold goldenrod
_CYAN = "\033[1;36m"
_GREEN = "\033[38;2;144;238;144m"  # light green
_RED = "\033[0;31m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_ITALIC = "\033[3m"
_RESET = "\033[0m"

# Fallback for terminals without true-color — detected via COLORTERM env var
_has_truecolor = os.environ.get("COLORTERM", "") in ("truecolor", "24bit")
if not _has_truecolor:
    _GOLD = "\033[1;33m"
    _GOLD_BRIGHT = "\033[1;93m"
    _GOLD_BOLD = "\033[1;33m"
    _GREEN = "\033[1;32m"
