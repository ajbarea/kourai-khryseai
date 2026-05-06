"""GUI agent registry — synthesises the legacy ``AGENTS`` dict from
``kourai_common.agents`` plus GUI-only enrichments (per-agent colors,
emoji-prefix detection, avatar paths).

Shared content (titles, descriptions, quotes, handoff lines, victory
lines) lives in ``shared/src/kourai_common/agents.py``. Existing GUI
callers continue to import ``AGENTS``, ``HANDOFF_LINES``,
``HANDOFF_GENERIC``, ``VICTORY_LINES``, ``detect_agent``,
``get_avatar_path`` from here unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kourai_common.agents import (
    AGENT_METADATA,
    AGENT_QUOTES,
    EMOJI_PREFIX as EMOJI_TO_AGENT,
    HANDOFF_FALLBACKS as HANDOFF_GENERIC,
    HANDOFF_LINES,
    VICTORY_LINES,
    detect_agent,
)
from kourai_common.paths import avatars_dir

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "AGENTS",
    "EMOJI_TO_AGENT",
    "HANDOFF_GENERIC",
    "HANDOFF_LINES",
    "VICTORY_LINES",
    "detect_agent",
    "get_avatar_path",
]

logger = logging.getLogger(__name__)

# Avatar images live in the root assets/avatars/anime directory
_AVATAR_DIR = avatars_dir()  # default style: anime


def get_avatar_path(name: str) -> Path | None:
    """Return the avatar image path for an agent, or None if not found."""
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        p = _AVATAR_DIR / f"{name}{ext}"
        logger.debug("Checking for avatar at: %s", p)
        if p.exists():
            logger.debug("Avatar found: %s", p)
            return p
    logger.debug("Avatar not found for: %s", name)
    return None


# GUI roster: the 6 main maidens. Puck and Cupid are still excluded from
# AGENTS (their portraits / panels aren't wired yet), but their colors
# now live alongside the rest in kourai_common.agents.AGENT_METADATA so
# the VN's hex_color lookup pattern works for all 8 agents on startup.
_GUI_ROSTER = ("hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme")
_AGENT_COLORS: dict[str, tuple[int, int, int]] = {
    name: AGENT_METADATA[name]["rgb"]  # type: ignore[misc]
    for name in _GUI_ROSTER
}


def _build_agents() -> dict[str, dict]:
    """Synthesise the legacy AGENTS dict from shared metadata + colors."""
    out: dict[str, dict] = {}
    for name, color in _AGENT_COLORS.items():
        meta = AGENT_METADATA.get(name, {})
        out[name] = {
            "title": meta.get("title", ""),
            "desc": meta.get("desc", ""),
            "color": color,
            "quotes": list(AGENT_QUOTES.get(name, [])),
            "user_quotes": list(meta.get("user_quotes", [])),
        }
    return out


# Legacy import shape: AGENTS["hephaestus"]["quotes"], etc.
AGENTS: dict[str, dict] = _build_agents()

# EMOJI_TO_AGENT and detect_agent above re-export from kourai_common.agents
# (shared with CLI's _EMOJI_TO_MAIDEN derivation in hosts/cli/maidens.py).
