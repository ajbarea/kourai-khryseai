"""Character data constants for the Golden Maidens (CLI).

Now imports from kourai_common.agents for centralized consistency.
"""

from __future__ import annotations

from kourai_common.agents import (
    AGENT_METADATA,
    AGENT_QUOTES,
    EMOJI_PREFIX,
    HANDOFF_FALLBACKS,
    HANDOFF_LINES,
    VICTORY_LINES,
)
from kourai_common.paths import avatars_dir

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

# Map Hephaestus executor emojis → (agent_name, maiden face).
# Derived from kourai_common.agents.EMOJI_PREFIX so a new agent's emoji
# shows up here automatically; the face comes from _MAIDEN_FACES above.
_EMOJI_TO_MAIDEN: dict[str, tuple[str, str]] = {
    emoji: (name, _MAIDEN_FACES.get(name, "")) for emoji, name in EMOJI_PREFIX.items()
}

# Handoff and Victory lines now use centralized lists (mapped to CLI names)
_HANDOFF_LINES = HANDOFF_LINES
_HANDOFF_GENERIC = HANDOFF_FALLBACKS
_VICTORY_LINES = VICTORY_LINES

# Asset directory for golden maiden portraits
_ASSETS_DIR = avatars_dir()  # default style: anime
