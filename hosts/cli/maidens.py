"""Character data constants for the Golden Maidens (CLI).

Now imports from kourai_common.agents for centralized consistency.
"""

from __future__ import annotations

from pathlib import Path

from kourai_common.agents import (
    AGENT_METADATA,
    AGENT_QUOTES,
    HANDOFF_FALLBACKS,
    HANDOFF_LINES,
    VICTORY_LINES,
)

# ---------------------------------------------------------------------------
# Banner & personality
# ---------------------------------------------------------------------------
_TAGLINES = [
    "The Golden Maidens await your command",
    "Forged in fire, refined by hand",
    "Automata of the divine forge",
    "Where craft meets intelligence",
    "Your gilded development companions",
    "Hephaestus' finest creations",
]

# Map centralized metadata to CLI-specific _MAIDENS dict
_MAIDENS: dict[str, dict] = {}
for name, meta in AGENT_METADATA.items():
    _MAIDENS[name] = {
        "face": "(╭∩╮)⊃━☆ﾟ.*･｡ﾟ" if name == "hephaestus" else "(◕ᴗ◕✿)",  # Fallback kaomoji
        "title": meta["title"],
        "desc": meta["desc"],
        "quotes": AGENT_QUOTES.get(name, []),
        "user_quotes": meta.get("user_quotes", []),
    }

# Apply specific kaomoji faces
_CLI_FACES = {
    "hephaestus": "(╭∩╮)⊃━☆ﾟ.*･｡ﾟ",
    "metis": "( ◡‿◡)✧",
    "techne": "( ⌐■_■)",
    "dokimasia": "(╯°□°)╯︵🐛",
    "kallos": "(◕ᴗ◕✿)",
    "mneme": "φ(◎ω◎)φ",
}
for name, face in _CLI_FACES.items():
    if name in _MAIDENS:
        _MAIDENS[name]["face"] = face

# Quick lookup: agent name → maiden face for inline status messages
_MAIDEN_FACES: dict[str, str] = {name: str(m["face"]) for name, m in _MAIDENS.items()}

# Map Hephaestus executor emojis → maiden faces for status message replacement
_EMOJI_TO_MAIDEN: dict[str, tuple[str, str]] = {
    "\U0001f525": ("hephaestus", _MAIDEN_FACES.get("hephaestus", "")),
    "\U0001f4d0": ("metis", _MAIDEN_FACES.get("metis", "")),
    "\u2699\ufe0f": ("techne", _MAIDEN_FACES.get("techne", "")),
    "\u2699": ("techne", _MAIDEN_FACES.get("techne", "")),
    "\U0001f9ea": ("dokimasia", _MAIDEN_FACES.get("dokimasia", "")),
    "\u2728": ("kallos", _MAIDEN_FACES.get("kallos", "")),
    "\U0001f4dc": ("mneme", _MAIDEN_FACES.get("mneme", "")),
}

# Handoff and Victory lines now use centralized lists (mapped to CLI names)
_HANDOFF_LINES = HANDOFF_LINES
_HANDOFF_GENERIC = HANDOFF_FALLBACKS
_VICTORY_LINES = VICTORY_LINES

# Asset directory for golden maiden portraits
_ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets" / "avatars" / "anime"
