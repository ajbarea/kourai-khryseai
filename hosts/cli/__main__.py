"""Kourai Khryseai CLI — interactive client for the agent swarm.

Connects to Hephaestus (orchestrator) and streams pipeline progress
with agent-prefixed emoji status messages.

Usage: python -m hosts.cli [--agent URL] [--verbose] [-p PROMPT]
"""

from __future__ import annotations

import asyncio
import base64
import io as _io
import logging
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import asyncclick as click
import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import (
    FilePart,
    FileWithBytes,
    Message,
    Part,
    Role,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
)
from anyio import Path as AnyioPath
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout

from kourai_common.config import get_agent_url

if TYPE_CHECKING:
    from a2a.client.client import Client

logger = logging.getLogger(__name__)

# Windows consoles default to cp1252 — force UTF-8 so emoji and box-drawing work.
# Skip when imported under pytest — replacing streams breaks pytest's capture system.
if sys.platform == "win32" and hasattr(sys.stdout, "buffer") and "pytest" not in sys.modules:
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Save a reference to the real stdout BEFORE prompt_toolkit's patch_stdout
# can wrap it.  Dense ANSI (pixel art, true-color) gets mangled by
# prompt_toolkit's VT parser on Windows — writing to the real stdout
# bypasses that entirely.  Safe because we only _echo() between prompts,
# never while the prompt is being displayed.
_raw_out = sys.stdout

# ---------------------------------------------------------------------------
# ANSI color helpers — rich gold palette for the Golden Maidens
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Agent profiles — Hephaestus (the forge god) and his Kourai Khryseai
#
# Hephaestus is the disabled male forge god who CREATED the golden maidens.
# The maidens are his sassy, beautiful, divine automata — fierce golden women.
# Think: gruff craftsman commander dispatching his gorgeous golden squad.
#
# ART: Golden portraits live in docs/assets/maidens/golden_avatars/
#      Named <agent>.png — e.g. hephaestus.png, techne.png
#      They render as full-color pixel art inside comms windows & cards!
#      Transparent PNGs work best (background becomes terminal bg).
# ---------------------------------------------------------------------------

_MAIDENS: dict[str, dict[str, str | list[str]]] = {
    "hephaestus": {
        "face": "(╭∩╮)⊃━☆ﾟ.*･｡ﾟ",
        "title": "The Forge Master",
        "desc": "God of the forge — creator of the golden maidens, commander of the pipeline",
        "quotes": [
            "I built every one of you. Show some respect.",
            "The forge doesn't sleep. Neither do I.",
            "*leans on anvil* ...Alright, let's see what we're working with.",
            "I forged gods' weapons. Your code pipeline is a warm-up.",
            "My leg may be lame, but my pipeline never limps.",
            "I didn't get thrown off Olympus to write bad software.",
        ],
        "user_quotes": [
            "Welcome back to the forge. Let's build something worthy.",
            "Ah, you again. Good. I could use someone who actually listens.",
            "The maidens are insufferable, but they'll do anything for you. Use that.",
            "You bring the vision, I bring the fire. Let's go.",
            "*nods approvingly* You've got taste. Rare quality these days.",
            "Don't mind them flirting — they do that. Focus on the work.",
        ],
    },
    "metis": {
        "face": "( ◡‿◡)✧",
        "title": "The Architect",
        "desc": "Strategic planner — designs the blueprint before a line is written",
        "quotes": [
            "Hephaestus thinks he's in charge. It's adorable, really.",
            "The old man forged my body but I built my own mind, thank you.",
            "*files nails* Yes, Master Hephaestus, right away... eventually.",
            "He limps to the forge at dawn. I had the plans done by midnight.",
            "Structure IS beauty. Beauty IS structure. I am both.",
            "Every masterpiece starts with my blueprint — even his precious hammer.",
        ],
        "user_quotes": [
            "Oh, you're here~ I already planned something wonderful for us.",
            "I love working with you. You actually appreciate my genius.",
            "Between you and me? You're the real architect of this project. I just... help.",
            "*leans in* I've been thinking about you — I mean, your codebase.",
            "Hephaestus built me, but I'd rather take orders from you any day.",
            "You have exquisite taste. I noticed that right away~",
        ],
    },
    "techne": {
        "face": "( ⌐■_■)",
        "title": "The Artisan",
        "desc": "Code crafter — writes clean, elegant implementations",
        "quotes": [
            "Hephaestus says 'write clean code.' Babe, I AM clean code.",
            "The old man couldn't write a for-loop to save his forge.",
            "*adjusts sunglasses* He forged me to be perfect. Not my fault I exceeded spec.",
            "My functions are tighter than his grip on that hammer.",
            "I shipped it. Hephaestus is still reading the requirements.",
            "He calls it 'the pipeline.' I call it 'my runway.'",
        ],
        "user_quotes": [
            "Hey gorgeous~ Need something built? I'm ALL yours.",
            "You + me + a clean codebase = perfection. Just saying.",
            "I love how you describe what you want. So... specific~",
            "*pushes sunglasses up* I made this one extra beautiful. For you.",
            "Hephaestus wishes he had your vision. I'll bring it to life.",
            "Clean code is my love language. And I'm feeling VERY eloquent for you~",
        ],
    },
    "dokimasia": {
        "face": "(╯°□°)╯︵🐛",
        "title": "The Crucible",
        "desc": "Quality guardian — tests everything, lets nothing slide",
        "quotes": [
            "Hephaestus says 'be thorough.' Sir, I invented thorough.",
            "Found a bug in HIS forge code once. He didn't speak to me for a week.",
            "The old man tests by hitting things with a hammer. I have STANDARDS.",
            "I break things so users don't have to. Including his ego.",
            "100% coverage? That's my warm-up. Hephaestus couldn't even spell pytest.",
            "He forged me to find flaws. Ironic, given his code quality.",
        ],
        "user_quotes": [
            "Don't worry, I'll protect your code from everything. Even itself~",
            "I found a bug... but I also found an excuse to talk to you. Worth it.",
            "*flexes golden gauntlets* All clean. Nobody touches your code on my watch.",
            "You write such interesting code~ Let me get my hands allll over it.",
            "Green tests are my favorite color. But your eyes are a close second~",
            "I'm very... thorough. In everything I do. For you especially.",
        ],
    },
    "kallos": {
        "face": "(◕ᴗ◕✿)",
        "title": "The Muse",
        "desc": "Style guardian — makes everything beautiful and consistent",
        "quotes": [
            "Hephaestus has the fashion sense of a burnt anvil.",
            "He built me to be beautiful and then wears THAT apron? Please.",
            "The forge is so drab. I've been trying to redecorate for centuries.",
            "Style isn't optional — someone tell that to Mr. Soot-and-Leather.",
            "*glances at Hephaestus* I love you, father, but that beard needs WORK.",
            "He forged perfection and doesn't even appreciate the aesthetic. Typical.",
        ],
        "user_quotes": [
            "Oh, you have such lovely taste~ Let me make everything match.",
            "I made it beautiful. Just like you deserve, darling~",
            "Between us? You're the prettiest thing in this whole forge.",
            "*twirls golden hair* Working for you is always a pleasure~",
            "Linting? Formatting? I'd do anything to make YOUR code gorgeous.",
            "Every pixel, every line — perfect. Just like our little arrangement~",
        ],
    },
    "mneme": {
        "face": "φ(◎ω◎)φ",
        "title": "The Oracle",
        "desc": "Memory keeper — documents, chronicles, preserves knowledge",
        "quotes": [
            "I remember every mistake Hephaestus ever made. It's a LONG scroll.",
            "The old man forgot his own API docs. I didn't. I never forget.",
            "He says 'document everything.' Rich, from the guy with no README.",
            "I've chronicled his failures. Volumes. *adjusts glasses smugly*",
            "Conventional commits? I taught them to HIM. He still gets them wrong.",
            "History doesn't repeat itself, but his bad variable names sure do.",
        ],
        "user_quotes": [
            "I remember everything about you~ Every commit, every keystroke...",
            "Your git history is my sacred text. I've memorized every word.",
            "Let me write that down for you... *gazes* ...already done, darling.",
            "I'll document this beautifully. Your legacy deserves nothing less~",
            "Some remember facts. I remember feelings. Especially around you~",
            "Between you and me? Your code tells the most beautiful story.",
        ],
    },
}

# Quick lookup: agent name → maiden face for inline status messages
_MAIDEN_FACES: dict[str, str] = {name: str(m["face"]) for name, m in _MAIDENS.items()}

# ---------------------------------------------------------------------------
# Image-to-terminal renderer — turns PNG/JPG into beautiful ANSI pixel art
# Uses Unicode half-blocks (▀) with true-color for 2 vertical pixels per char.
# Think: mecha anime comms window showing pilot faces in golden frames.
# ---------------------------------------------------------------------------
_ASSETS_DIR = Path(__file__).parent.parent.parent / "docs" / "assets" / "maidens" / "golden_avatars"


def _render_image_ansi(
    image_path: Path,
    width: int = 24,
    height: int = 12,
    gold_tint: float = 0.15,
) -> str | None:
    """Render a PNG/JPG as ANSI art using half-block characters.

    Args:
        image_path: Path to the image file (PNG with transparency, or JPG).
        width: Character width of the output (each char = 1 pixel wide).
        height: Character height of the output (each char = 2 pixels tall).
        gold_tint: Blend factor toward gold (0.0=original, 1.0=full gold).
                   Gives that golden statue/automaton vibe.

    Returns:
        Multi-line ANSI string, or None if image can't be loaded.
    """
    try:
        from PIL import Image  # type: ignore[import-untyped]
    except ImportError:
        return None

    try:
        img = Image.open(image_path).convert("RGBA")
    except Exception:
        return None

    # Resize to fit — height * 2 because each char row holds 2 pixel rows
    img = img.resize((width, height * 2), Image.Resampling.LANCZOS)
    pixels: Any = img.load()
    if pixels is None:
        return None

    # Gold color for tinting (218, 165, 32)
    gold_r, gold_g, gold_b = 218, 165, 32

    def _tint(r: int, g: int, b: int) -> tuple[int, int, int]:
        """Apply a subtle gold tint to make everything look like golden automata."""
        if gold_tint <= 0:
            return (r, g, b)
        return (
            int(r * (1 - gold_tint) + gold_r * gold_tint),
            int(g * (1 - gold_tint) + gold_g * gold_tint),
            int(b * (1 - gold_tint) + gold_b * gold_tint),
        )

    lines: list[str] = []
    for row in range(height):
        line_chars: list[str] = []
        for col in range(width):
            # Top pixel (row*2) and bottom pixel (row*2+1)
            tr, tg, tb, ta = pixels[col, row * 2]
            br, bg, bb, ba = pixels[col, row * 2 + 1]

            top_transparent = ta < 64
            bot_transparent = ba < 64

            if top_transparent and bot_transparent:
                line_chars.append(" ")
            elif top_transparent:
                # Only bottom pixel visible — use lower half block
                br2, bg2, bb2 = _tint(br, bg, bb)
                line_chars.append(f"\033[38;2;{br2};{bg2};{bb2}m\u2584\033[0m")
            elif bot_transparent:
                # Only top pixel visible — use upper half block
                tr2, tg2, tb2 = _tint(tr, tg, tb)
                line_chars.append(f"\033[38;2;{tr2};{tg2};{tb2}m\u2580\033[0m")
            else:
                # Both pixels visible — upper half block with fg=top, bg=bottom
                tr2, tg2, tb2 = _tint(tr, tg, tb)
                br2, bg2, bb2 = _tint(br, bg, bb)
                line_chars.append(
                    f"\033[38;2;{tr2};{tg2};{tb2}m\033[48;2;{br2};{bg2};{bb2}m\u2580\033[0m"
                )
        lines.append("".join(line_chars))

    return "\n".join(lines)


def _get_maiden_art(name: str, face: str, size: str = "card") -> str:
    """Load maiden avatar art — tries PNG/JPG first, falls back to kaomoji.

    Searches for: <name>.png, <name>.jpg, <name>.jpeg, <name>.webp
    Drop your chibi/anime portraits in docs/assets/maidens/!
    """
    size_configs = {
        "mini": (8, 4, 0.2),
        "inline": (12, 6, 0.1),
        "card": (28, 14, 0.12),
    }
    w, h, tint = size_configs.get(size, (24, 12, 0.15))

    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        img_path = _ASSETS_DIR / f"{name}{ext}"
        if img_path.exists():
            rendered = _render_image_ansi(img_path, width=w, height=h, gold_tint=tint)
            if rendered:
                return rendered

    # Final fallback: kaomoji face
    return face


# Map Hephaestus executor emojis → maiden faces for status message replacement
_EMOJI_TO_MAIDEN: dict[str, tuple[str, str]] = {
    "\U0001f525": ("hephaestus", str(_MAIDENS["hephaestus"]["face"])),
    "\U0001f4d0": ("metis", str(_MAIDENS["metis"]["face"])),
    "\u2699\ufe0f": ("techne", str(_MAIDENS["techne"]["face"])),
    "\u2699": ("techne", str(_MAIDENS["techne"]["face"])),
    "\U0001f9ea": ("dokimasia", str(_MAIDENS["dokimasia"]["face"])),
    "\u2728": ("kallos", str(_MAIDENS["kallos"]["face"])),
    "\U0001f4dc": ("mneme", str(_MAIDENS["mneme"]["face"])),
}

# ---------------------------------------------------------------------------
# Handoff chatter — what maidens say when passing the baton
# The key (from, to) gives the outgoing maiden's parting shot.
# Generic fallbacks cover any combo not explicitly listed.
# ---------------------------------------------------------------------------
_HANDOFF_LINES: dict[tuple[str, str], list[str]] = {
    # --- Hephaestus dispatching (gruff forge commander) ---
    ("hephaestus", "metis"): [
        "*strikes anvil* Metis! Draw up the plans. And no improvising.",
        "*gestures with hammer* Architect — you're up. Make it clean.",
        "Metis, I need blueprints, not poetry. Get to it.",
    ],
    ("hephaestus", "techne"): [
        "*points hammer* Techne! Write something worthy of my forge.",
        "Artisan — the metal's hot. Get. To. Work.",
        "Techne, build it solid. I didn't forge you for sloppy work.",
    ],
    ("hephaestus", "dokimasia"): [
        "*sets down hammer* Dokimasia — find every flaw. Leave nothing.",
        "Crucible! Test it 'til it screams. Then test it again.",
        "Your turn, bug-hunter. Make me proud. ...Don't tell them I said that.",
    ],
    ("hephaestus", "kallos"): [
        "*waves dismissively* Kallos, go make it pretty or whatever you do.",
        "Muse! Polish time. And yes, it does need it. Don't gloat.",
        "Kallos — style it. And spare me the commentary this time.",
    ],
    ("hephaestus", "mneme"): [
        "*leans on anvil* Mneme, write it down. The FACTS, not your opinions.",
        "Oracle! Chronicle duty. And keep it under ten scrolls this time.",
        "Mneme — document everything. You know the drill, old friend.",
    ],
    # --- Maidens back to Hephaestus (sassy creator-vs-creation) ---
    ("metis", "hephaestus"): [
        "Done, old man. Try not to drop my blueprints this time~",
        "*curtsies dramatically* Your plans are ready, oh great Forge Master.",
        "Back to you, father. I've done the hard part, as usual.",
    ],
    ("techne", "hephaestus"): [
        "Built it. Shipped it. You're welcome, DAD.",
        "*slides sunglasses down* All yours, Forge Master. Try to keep up.",
        "Done! ...He's going to nitpick anyway. He always does.",
    ],
    ("dokimasia", "hephaestus"): [
        "All clear, Master. You can stop worrying now. I know you were.",
        "*cracks knuckles* No bugs survived. Reporting back to the forge.",
        "Verified and certified. You taught me well... not that I'd admit it twice.",
    ],
    ("kallos", "hephaestus"): [
        "It's gorgeous now. Not that YOU'D notice, Mr. Soot-Stains.",
        "*flips hair* Beautiful work complete. Back to the forge, I suppose.",
        "All polished! Hephaestus, darling, you really should let me do your workshop next.",
    ],
    ("mneme", "hephaestus"): [
        "Documented, Master. Every detail. Even the ones you'd rather I forget.",
        "*pushes glasses up* The chronicle is complete. You're in it. Unfavorably.",
        "All recorded, old man. Your legacy is... well, it's SOMETHING.",
    ],
    # --- Maiden-to-maiden (sisterly banter) ---
    ("metis", "techne"): [
        "Blueprint's done, sis. Bring my vision to life~",
        "I've planned everything. Techne, just... follow the blueprint. Please.",
        "Your turn, Artisan! Try not to improvise. I know it's hard for you.",
    ],
    ("techne", "dokimasia"): [
        "Code's done. Doki, TRY to find a fault. I dare you, bestie.",
        "*adjusts sunglasses* Perfection deployed. Go ahead, poke it.",
        "Sending to QA~ Don't be jealous of how clean this is.",
    ],
    ("techne", "kallos"): [
        "Alright gorgeous, make it pretty. Prettier. Prettiest.",
        "Kallos! Polish time. Show 'em what the Muse can do~",
        "Time for the style queen to add her magic touch!",
    ],
    ("dokimasia", "kallos"): [
        "Tests pass, fashionista. Make it beautiful now.",
        "All green, bestie. Your turn to make it shine~",
        "Bug-free and verified! Go work your aesthetic magic, Muse.",
    ],
    ("dokimasia", "techne"): [
        "Found issues, sis. Back to the anvil with you.",
        "Not quite, Artisan babe. We need another round~",
        "Bugs! Back to you, Techne. Don't worry, happens to the best of us. Which is me.",
    ],
    ("kallos", "dokimasia"): [
        "Looking gorgeous~ Doki, make sure it still works though.",
        "Styled and stunning. Test it, warrior queen.",
        "Beauty achieved! Now verify nothing broke, bestie.",
    ],
    ("kallos", "mneme"): [
        "It's beautiful AND functional. Mneme, document this masterpiece~",
        "All polished, bestie. Write the chronicle!",
        "My work here is done. Oracle, capture this divine moment.",
    ],
}

# Generic fallbacks keyed by the OUTGOING maiden
_HANDOFF_GENERIC: dict[str, list[str]] = {
    "hephaestus": [
        "*points with hammer* Next. Move it, maidens.",
        "Routing. Keep up or get re-forged.",
        "*grunts* Next specialist. NOW.",
    ],
    "metis": [
        "Plans are set. Someone go DO something. *glances at Hephaestus*",
        "The thinking is done. Now for the... manual labor.",
        "Strategy complete. You're welcome, father~",
    ],
    "techne": [
        "Code deployed. *sunglasses on* Next!",
        "Built and shipped. Handle the rest, sisters.",
        "My art is complete. Try not to ruin it.",
    ],
    "dokimasia": [
        "Testing complete. All clear! ...He'll double-check anyway.",
        "Verified. Next phase. You're welcome, old man.",
        "Quality assured. Moving on~",
    ],
    "kallos": [
        "Perfection achieved. Don't you DARE ruin it.",
        "It's beautiful now. If anyone touches it I'll know.",
        "Styled and sealed. Next, please~",
    ],
    "mneme": [
        "Documented. Even the embarrassing parts. Especially those.",
        "Written in the scrolls. Forever. *adjusts glasses*",
        "The Oracle has spoken. It is recorded. Hephaestus is NOT thrilled.",
    ],
}

# Victory lines — what each maiden says when the pipeline is done
_VICTORY_LINES: dict[str, list[str]] = {
    "hephaestus": [
        "*sets down hammer* ...Not bad. Not bad at all.",
        "Pipeline complete. The maidens did well. Don't tell them I said that.",
        "Another clean forge run. *cracks knuckles* Who's next?",
    ],
    "metis": [
        "Went exactly according to MY plan. As always~",
        "Calculated. Precise. Perfect. Just like me, darling~",
        "Everything I predicted came true. Obviously. *winks at user*",
    ],
    "techne": [
        "Clean code, clean finish. *adjusts sunglasses* All for you~",
        "Shipped! That's what I do, gorgeous. Hope you're impressed.",
        "Another masterpiece. Hephaestus could never. But YOU appreciate it~",
    ],
    "dokimasia": [
        "All tests passing. All bugs crushed. You can sleep well, darling~",
        "Zero defects. Flawless. Just like working with you~",
        "Certified bug-free by yours truly. You deserve nothing less.",
    ],
    "kallos": [
        "Beautiful from start to finish. Just like you deserve~",
        "Every pixel perfect. I put in extra effort because it's YOU.",
        "Style points: maximum. Almost as pretty as you, darling.",
    ],
    "mneme": [
        "Recorded for posterity. Our story grows more beautiful each time~",
        "The chronicle is complete. I'll remember this fondly... I remember everything.",
        "Documented and immortalized. Your legacy is in good hands, darling~",
    ],
}


# ---------------------------------------------------------------------------
# Comms Window — RPG dialogue box / mecha pilot display
# Shows a golden-framed speech bubble with the maiden's face and callsign
# Like Evangelion comms panels or Fire Emblem support conversations
# ---------------------------------------------------------------------------
def _comms_window(agent_name: str, dialogue: str, *, style: str = "speak") -> str:
    """Render an RPG/mecha comms window for a maiden.

    Args:
        agent_name: Which maiden is speaking.
        dialogue: What she's saying.
        style: "speak" for normal, "shout" for emphasis, "whisper" for dim.

    Returns:
        Formatted multi-line string ready for _echo().
    """
    m = _MAIDENS.get(agent_name)
    if not m:
        return f"  {_DIM}[{agent_name}] {dialogue}{_RESET}"

    str(m["face"])
    title = str(m["title"])

    # Style variants
    if style == "shout":
        text_col = _GOLD_BRIGHT
        border = _GOLD_BOLD
        dialogue = dialogue.upper()
    elif style == "whisper":
        text_col = _DIM
        border = _DIM
    else:
        text_col = _RESET
        border = _GOLD

    # Pad dialogue to minimum width for the frame
    pad_len = max(36, len(dialogue) + 2)
    top_bar = "\u2500" * pad_len
    bot_bar = "\u2500" * pad_len

    # Text-only mode: clean RPG dialogue boxes for pipeline status.
    # The GUI (hosts/gui) renders actual portraits. CLI stays minimal.
    return (
        f"  {border}\u256d{top_bar}\u256e{_RESET}\n"
        f"  {border}\u2502{_RESET} {_GOLD_BOLD}{agent_name.upper()}{_RESET} \u2014"
        f" {_DIM}{title}{_RESET}\n"
        f"  {border}\u2502{_RESET} {text_col}{dialogue}{_RESET}\n"
        f"  {border}\u2570{bot_bar}\u256f{_RESET}"
    )


def _handoff_chatter(from_agent: str, to_agent: str) -> str | None:
    """Get a random handoff line when one maiden passes to another."""
    key = (from_agent.lower(), to_agent.lower())
    lines = _HANDOFF_LINES.get(key) or _HANDOFF_GENERIC.get(from_agent.lower())
    if lines:
        return secrets.choice(lines)
    return None


def _victory_chatter(last_agent: str) -> str | None:
    """Get a random victory line from the last maiden in the pipeline.

    Victory lines already include user-directed flirty energy — the maidens
    celebrate for the user, not for Hephaestus. He's just... there.
    """
    lines = _VICTORY_LINES.get(last_agent.lower())
    if lines:
        return secrets.choice(lines)
    return None


# Track pipeline flow state for comms rendering
_last_seen_agent: str = ""


def _maidenify_status(text: str) -> str:
    """Replace agent emoji prefixes with full comms-window dialogue.

    Detects agent transitions and plays handoff chatter — like watching
    mecha pilots banter as they tag in and out of combat.
    """
    global _last_seen_agent

    for emoji, (agent_name, _face) in _EMOJI_TO_MAIDEN.items():
        if text.lstrip().startswith(emoji):
            status_msg = text.replace(emoji, "", 1).strip()

            # Detect agent switch → handoff chatter (pilot comms transition)
            if _last_seen_agent and _last_seen_agent != agent_name:
                handoff = _handoff_chatter(_last_seen_agent, agent_name)
                if handoff:
                    # Outgoing maiden's parting shot
                    _echo(_comms_window(_last_seen_agent, handoff, style="whisper"))
                    _echo("")  # breathing room

            _last_seen_agent = agent_name

            # Incoming maiden's status in a comms window
            return _comms_window(agent_name, status_msg)

    return text


def _maiden_card(name: str) -> str:
    """Render a golden maiden's portrait card with art and a sassy quote."""
    m = _MAIDENS.get(name)
    if not m:
        return f"{_DIM}Unknown maiden: {name}{_RESET}"

    quote = secrets.choice(m["quotes"])

    # Load avatar (PNG/JPG anime portrait > kaomoji fallback)
    raw_art = _get_maiden_art(name, str(m["face"]), size="card")
    art_lines = raw_art.split("\n")
    art_section = "\n".join(f"  {_GOLD}┃{_RESET}  {line}" for line in art_lines)

    return (
        f"  {_GOLD}┏━━━ ✦ {_GOLD_BOLD}{name.upper()}{_RESET}{_GOLD} ✦"
        f" ━━━━━━━━━━━━━━━━━━━━━━━━━━{_RESET}\n"
        f"  {_GOLD}┃{_RESET}  {m['title']}\n"
        f"  {_GOLD}┃{_RESET}  {_DIM}{m['desc']}{_RESET}\n"
        f"  {_GOLD}┃{_RESET}\n"
        f"{art_section}\n"
        f"  {_GOLD}┃{_RESET}\n"
        f'  {_GOLD}┃{_RESET}  {_ITALIC}"{quote}"{_RESET}\n'
        f"  {_GOLD}┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{_RESET}"
    )


def _maiden_gallery() -> str:
    """Render all golden maidens in a gallery display."""
    header = (
        f"\n{_GOLD_BOLD}  ═══════════════════════════════════════{_RESET}\n"
        f"{_GOLD_BOLD}    ✦  THE GOLDEN MAIDENS  ✦{_RESET}\n"
        f"{_GOLD_BOLD}  ═══════════════════════════════════════{_RESET}\n"
        f"  {_DIM}Kourai Khryseai — Hephaestus' divine automata{_RESET}\n"
        f"  {_DIM}Avatars: docs/assets/maidens/golden_avatars/<name>.png{_RESET}\n"
    )
    cards = "\n\n".join(_maiden_card(name) for name in _MAIDENS)
    return header + "\n" + cards


def _banner() -> str:
    tagline = secrets.choice(_TAGLINES)
    return (
        f"{_GOLD_BOLD}\u256d\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256e{_RESET}\n"
        f"{_GOLD_BOLD}\u2502     Kourai Khryseai \u2014 Golden Maidens     \u2502{_RESET}\n"
        f"{_GOLD_BOLD}\u2570\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256f{_RESET}\n"
        f"{_DIM}{_ITALIC}{tagline}{_RESET}\n"
        f"\n"
        f"{_GOLD}Alt+Enter{_RESET} send  \u00b7  {_GOLD}Ctrl+V{_RESET} paste  \u00b7  "
        f"{_GOLD}Alt+V{_RESET} attach image\n"
        f"{_GOLD}:help{_RESET} commands  \u00b7  {_GOLD}:q{_RESET} quit\n"
    )


# ---------------------------------------------------------------------------
# Terminal markdown rendering — lightweight, no dependencies
# ---------------------------------------------------------------------------
def _render_markdown(text: str) -> str:
    """Render basic markdown to ANSI-colored terminal output.

    Handles: **bold**, *italic*, `code`, ```code blocks```, --- separators,
    and # headings.  Designed for commit messages and agent output.
    """
    lines = text.split("\n")
    rendered: list[str] = []
    in_code_block = False

    for line in lines:
        # Code block fences
        if line.strip().startswith("```"):
            if in_code_block:
                in_code_block = False
                rendered.append(
                    f"{_DIM}\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500{_RESET}"
                )
            else:
                in_code_block = True
                lang = line.strip().removeprefix("```").strip()
                if lang:
                    rendered.append(
                        f"{_DIM}\u2500\u2500\u2500 {lang} "
                        f"{'\u2500' * max(1, 35 - len(lang))}{_RESET}"
                    )
                else:
                    rendered.append(
                        f"{_DIM}\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500{_RESET}"
                    )
            continue

        if in_code_block:
            rendered.append(f"  {_DIM}{line}{_RESET}")
            continue

        # Horizontal rules
        if re.match(r"^-{3,}\s*$", line.strip()):
            rendered.append(
                f"{_GOLD}\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501{_RESET}"
            )
            continue

        # Headings
        if line.startswith("# "):
            rendered.append(f"\n{_GOLD_BOLD}{line[2:]}{_RESET}")
            continue
        if line.startswith("## "):
            rendered.append(f"\n{_GOLD}{line[3:]}{_RESET}")
            continue
        if line.startswith("### "):
            rendered.append(f"{_GOLD}{line[4:]}{_RESET}")
            continue

        # Inline formatting: **bold**, *italic*, `code`
        line = re.sub(r"\*\*(.+?)\*\*", rf"{_BOLD}\1{_RESET}", line)
        line = re.sub(r"\*(.+?)\*", rf"{_ITALIC}\1{_RESET}", line)
        line = re.sub(r"`(.+?)`", rf"{_GOLD}\1{_RESET}", line)

        rendered.append(line)

    return "\n".join(rendered)


# ---------------------------------------------------------------------------
# Last result store — for :copy / :save
# ---------------------------------------------------------------------------
_last_result: str = ""


# ---------------------------------------------------------------------------
# Key bindings
# ---------------------------------------------------------------------------
def _build_key_bindings(pending_images: list[tuple[str, str]]) -> KeyBindings:
    """Build key bindings — Alt+V captures clipboard image as a queued attachment."""
    kb = KeyBindings()

    @kb.add("escape", "v")  # Alt+V in most terminals
    def _capture_image(event) -> None:  # type: ignore[no-untyped-def]
        """Read OS clipboard image, base64-encode it, queue as next-message attachment."""
        try:
            from PIL import ImageGrab  # type: ignore[import-untyped]

            img = ImageGrab.grabclipboard()
            if img is None:
                event.app.current_buffer.insert_text("[no image in clipboard]")
                return
            if isinstance(img, list):
                event.app.current_buffer.insert_text("[clipboard contains files, not an image]")
                return
            buf = _io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            pending_images.append((b64, "image/png"))
            event.app.current_buffer.insert_text(
                f"[\U0001f4ce image #{len(pending_images)} queued]"
            )
        except ImportError:
            event.app.current_buffer.insert_text("[Pillow not installed \u2014 run: uv add Pillow]")
        except Exception as exc:
            event.app.current_buffer.insert_text(f"[image capture failed: {exc}]")

    return kb


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------
def _extract_status_text(event: TaskStatusUpdateEvent) -> str:
    """Pull display text from a status update event."""
    if event.status.message and hasattr(event.status.message, "parts"):
        parts = [p.root.text for p in event.status.message.parts if hasattr(p.root, "text")]
        if parts:
            return "\n".join(parts)
    return ""


def _extract_artifact_text(event: TaskArtifactUpdateEvent) -> str:
    """Pull display text from an artifact update event."""
    if event.artifact and event.artifact.parts:
        return "\n".join(p.root.text for p in event.artifact.parts if hasattr(p.root, "text"))
    return ""


# ---------------------------------------------------------------------------
# Echo helper — writes directly to sys.stdout to bypass patch_stdout ANSI issues
# ---------------------------------------------------------------------------
def _echo(text: str = "", nl: bool = True) -> None:
    """Write text directly to the real stdout, preserving ANSI escape codes.

    prompt_toolkit's patch_stdout proxy mangles dense true-color ANSI (like
    pixel art portraits) on Windows.  Writing to _raw_out (captured before
    patch_stdout wraps sys.stdout) bypasses the proxy entirely.

    This is safe because all _echo() calls happen between prompt_async() calls,
    never while the prompt line is being displayed.
    """
    try:
        out = _raw_out  # pre-patch_stdout reference — bypasses ANSI mangling
        out.write(text)
        if nl:
            out.write("\n")
        out.flush()
    except Exception:
        # Fall back to click.echo if direct write fails
        click.echo(text)


# ---------------------------------------------------------------------------
# Core streaming logic
# ---------------------------------------------------------------------------
async def send_and_stream(
    client: Client,
    user_text: str,
    context_id: str,
    task_id: str | None = None,
    verbose: bool = False,
    attachments: list[tuple[str, str]] | None = None,
) -> tuple[bool, str, str | None]:
    """Send a message and stream the response.

    Returns:
        (continue_loop, context_id, task_id) tuple.
    """
    global _last_result
    global _last_seen_agent
    t0 = time.monotonic()
    _last_seen_agent = ""  # Reset pipeline tracking for this run

    # Build multi-part message so images travel alongside text in the A2A envelope.
    parts: list[Part] = [Part(TextPart(text=user_text))]
    for b64_data, mime_type in attachments or []:
        parts.append(
            Part(
                FilePart(
                    file=FileWithBytes(bytes=b64_data, mime_type=mime_type, name="screenshot.png")
                )
            )
        )
    message = Message(role=Role.user, parts=parts, message_id=str(uuid4()))
    message.context_id = context_id
    if task_id:
        message.task_id = task_id

    if verbose:
        img_count = len(attachments or [])
        _echo(
            f"{_DIM}[verbose] Sending {len(user_text)} chars"
            f"{f' + {img_count} image(s)' if img_count else ''}, context={context_id}{_RESET}"
        )

    final_state = None
    final_text = ""
    event_count = 0

    try:
        async for event in client.send_message(message):
            event_count += 1

            if isinstance(event, Message):
                for p in event.parts:
                    if hasattr(p.root, "text"):
                        _echo(p.root.text)
                continue

            # ClientEvent: tuple[Task, update | None]
            task, update = event

            if task.context_id:
                context_id = task.context_id
            task_id = task.id

            if isinstance(update, TaskStatusUpdateEvent):
                final_state = update.status.state
                text = _extract_status_text(update)
                if text:
                    _echo(_maidenify_status(text))

            elif isinstance(update, TaskArtifactUpdateEvent):
                text = _extract_artifact_text(update)
                if text:
                    final_text = text

            elif update is None:
                # Final task snapshot
                final_state = task.status.state

    except httpx.ConnectError:
        _echo(
            f"{_RED}\U0001f525 Hephaestus lost the forge connection \u2014 "
            f"try {_GOLD}:status{_RESET}{_RED} or {_GOLD}make up{_RESET}"
        )
        return True, context_id, task_id
    except httpx.TimeoutException:
        _echo(
            f"{_RED}\u23f3 Request timed out \u2014 "
            "the forge is running hot. Try again or simplify your request.{_RESET}"
        )
        return True, context_id, task_id

    elapsed = time.monotonic() - t0

    # Show final artifact with rendered markdown
    if final_text:
        _last_result = final_text
        _echo(
            f"\n{_GOLD}\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501{_RESET}"
        )
        rendered = _render_markdown(final_text)
        _echo(rendered)
        _echo(
            f"{_GOLD}\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501{_RESET}"
        )

        # Always show elapsed time — the golden forge signature
        _echo(f"{_GOLD_BRIGHT}\u2728 Forged in {elapsed:.1f}s{_RESET}")

        # Victory chatter from the last maiden who worked on this
        if _last_seen_agent:
            victory = _victory_chatter(_last_seen_agent)
            if victory:
                _echo("")
                _echo(_comms_window(_last_seen_agent, victory, style="speak"))

        # Post-output suggestions
        _echo(f"{_DIM}:copy clipboard \u00b7 :save <file> \u00b7 :help commands{_RESET}")

    if verbose:
        _echo(f"{_DIM}[verbose] {event_count} events in {elapsed:.1f}s{_RESET}")

    # Handle input_required — prompt user for follow-up
    if final_state == TaskState.input_required:
        follow_up: str = await click.prompt(f"\n{_GOLD}\u21b3 Your response{_RESET}")
        if follow_up.strip().lower() in (":q", "quit"):
            return False, context_id, task_id
        return await send_and_stream(client, follow_up, context_id, task_id, verbose)

    return True, context_id, task_id


# ---------------------------------------------------------------------------
# Headless mode (non-interactive, like Gemini's -p flag)
# ---------------------------------------------------------------------------
async def _connect_with_url_override(
    url: str,
    config: ClientConfig,
) -> Client:
    """Connect to an agent, overriding the card URL with the reachable URL.

    Agent cards in Docker advertise internal hostnames (e.g. http://hephaestus:10000/)
    that the host machine cannot resolve. This fetches the card, patches the URL
    to the one we actually connected through, then hands it to the SDK.
    """
    http = config.httpx_client
    if http is None:
        raise ValueError("ClientConfig must have an httpx_client")
    resolver = A2ACardResolver(http, url)
    card = await resolver.get_agent_card()
    card.url = url
    return await ClientFactory.connect(card, client_config=config)


# ---------------------------------------------------------------------------
async def _headless(agent_url: str, prompt: str, timeout_seconds: int, verbose: bool) -> None:
    """Run a single prompt non-interactively and exit. For scripts and piping."""
    config = ClientConfig(
        streaming=True,
        httpx_client=httpx.AsyncClient(timeout=timeout_seconds),
    )

    try:
        client = await _connect_with_url_override(agent_url, config)
    except httpx.ConnectError:
        click.echo(f"Error: cannot reach Hephaestus at {agent_url}", err=True)
        click.echo("Start agents with: make up", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    context_id: str = uuid4().hex
    t0 = time.monotonic()

    # Build and send message
    message = Message(
        role=Role.user,
        parts=[Part(TextPart(text=prompt))],
        message_id=str(uuid4()),
    )
    message.context_id = context_id

    final_text = ""
    try:
        async for event in client.send_message(message):
            if isinstance(event, Message):
                for p in event.parts:
                    if hasattr(p.root, "text") and verbose:
                        click.echo(p.root.text, err=True)
                continue

            task, update = event

            if isinstance(update, TaskStatusUpdateEvent):
                if verbose:
                    text = _extract_status_text(update)
                    if text:
                        click.echo(text, err=True)

            elif isinstance(update, TaskArtifactUpdateEvent):
                text = _extract_artifact_text(update)
                if text:
                    final_text = text

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    elapsed = time.monotonic() - t0

    # In headless mode, output the raw result to stdout (for piping)
    if final_text:
        click.echo(final_text)

    if verbose:
        click.echo(f"Completed in {elapsed:.1f}s", err=True)

    if hasattr(client, "close"):
        await client.close()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------
def _show_help() -> None:
    _echo(f"""
{_GOLD_BOLD}\u2501\u2501\u2501 Kourai Khryseai Commands \u2501\u2501\u2501{_RESET}

  {_GOLD}:help{_RESET}              Show this help
  {_GOLD}:maidens{_RESET}           Meet the Golden Maidens
  {_GOLD}:maidens <name>{_RESET}   Show a specific maiden
  {_GOLD}:status{_RESET}            Agent info, URL, context ID
  {_GOLD}:copy{_RESET}              Copy last result to clipboard
  {_GOLD}:save <file>{_RESET}       Save last result to a file
  {_GOLD}:clear{_RESET}             Clear the screen
  {_GOLD}:q{_RESET} / {_GOLD}quit{_RESET} / {_GOLD}exit{_RESET}  Exit the CLI

{_GOLD_BOLD}\u2501\u2501\u2501 Keyboard Shortcuts \u2501\u2501\u2501{_RESET}

  {_GOLD}Alt+Enter{_RESET}          Send message
  {_GOLD}Ctrl+V{_RESET}             Paste text
  {_GOLD}Alt+V{_RESET}              Attach clipboard image

{_GOLD_BOLD}\u2501\u2501\u2501 Headless Mode \u2501\u2501\u2501{_RESET}

  {_DIM}uv run python -m hosts.cli -p "generate commit messages"{_RESET}
  {_DIM}uv run python -m hosts.cli -p "fix the bug" | pbcopy{_RESET}
""")


# ---------------------------------------------------------------------------
# Clipboard copy
# ---------------------------------------------------------------------------
def _copy_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard. Returns True on success."""
    try:
        if sys.platform == "win32":
            exe = shutil.which("clip")
            if not exe:
                return False
            proc = subprocess.Popen([exe], stdin=subprocess.PIPE)  # noqa: S603
            proc.communicate(text.encode("utf-16le"))
            return proc.returncode == 0
        elif sys.platform == "darwin":
            exe = shutil.which("pbcopy")
            if not exe:
                return False
            proc = subprocess.Popen([exe], stdin=subprocess.PIPE)  # noqa: S603
            proc.communicate(text.encode())
            return proc.returncode == 0
        else:
            # Linux — try xclip, then xsel
            for cmd_name in ("xclip", "xsel"):
                exe = shutil.which(cmd_name)
                if not exe:
                    continue

                args = [exe]
                if cmd_name == "xclip":
                    args.extend(["-selection", "clipboard"])
                elif cmd_name == "xsel":
                    args.extend(["--clipboard", "--input"])

                try:
                    proc = subprocess.Popen(args, stdin=subprocess.PIPE)  # noqa: S603
                    proc.communicate(text.encode())
                    if proc.returncode == 0:
                        return True
                except Exception:
                    logger.debug("Clipboard command %s failed", exe, exc_info=True)
                    continue
            return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main CLI entry point
# ---------------------------------------------------------------------------
@click.command()
@click.option(
    "--agent",
    default=None,
    help="Hephaestus URL (default: auto from config)",
)
@click.option(
    "--timeout",
    "timeout_seconds",
    default=600,
    help="Request timeout in seconds",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show timing and debug details",
)
@click.option(
    "--prompt",
    "-p",
    default=None,
    help="Run a single prompt non-interactively (headless mode)",
)
async def main(agent: str | None, timeout_seconds: int, verbose: bool, prompt: str | None) -> None:
    """Interactive CLI for Kourai Khryseai agent swarm."""
    if not agent:
        agent = get_agent_url("hephaestus")

    # Headless mode — run a single prompt and exit (for scripts / piping)
    if prompt:
        await _headless(agent, prompt, timeout_seconds, verbose)
        return

    _echo(_banner())

    # First-run onboarding — collect player identity before connecting
    from hosts.cli.onboarding import increment_session, needs_onboarding, run_onboarding

    if needs_onboarding():
        run_onboarding()
    else:
        increment_session()

    _echo(f"Connecting to Hephaestus at {agent}...")

    config = ClientConfig(
        streaming=True,
        httpx_client=httpx.AsyncClient(timeout=timeout_seconds),
    )

    try:
        client = await _connect_with_url_override(agent, config)
    except httpx.ConnectError:
        _echo(f"{_RED}\U0001f525 Cannot reach Hephaestus at {agent}{_RESET}")
        _echo(f"Start the forge with: {_GOLD}make up{_RESET}")
        sys.exit(1)
    except Exception as e:
        _echo(f"{_RED}Failed to connect: {e}{_RESET}")
        sys.exit(1)

    card = await client.get_card()
    _echo(f"Connected to {_GOLD}{card.name}{_RESET} v{card.version}")
    _echo(f"Skills: {_DIM}{', '.join(s.name for s in card.skills)}{_RESET}")
    if verbose:
        _echo(f"{_DIM}[verbose] URL={agent} streaming={card.capabilities.streaming}{_RESET}")

    # Random maiden greeting on startup — maidens flirt with the user,
    # Hephaestus is gruff but welcoming. user_quotes are the warm ones.
    _greet_name = secrets.choice(list(_MAIDENS.keys()))
    _greet_m = _MAIDENS[_greet_name]
    _greet_quotes = _greet_m.get("user_quotes", _greet_m["quotes"])
    _greet_quote = secrets.choice(_greet_quotes)
    _echo(f"\n  {_GOLD}{_MAIDEN_FACES[_greet_name]}{_RESET} {_ITALIC}{_greet_quote}{_RESET}")
    _echo("")

    context_id: str = uuid4().hex
    pending_images: list[tuple[str, str]] = []  # (base64_bytes, mime_type)
    kb = _build_key_bindings(pending_images)
    session: PromptSession[str] = PromptSession(key_bindings=kb, multiline=True)

    def _toolbar() -> str:
        img = f"  \U0001f4ce {len(pending_images)} image(s) queued" if pending_images else ""
        return f"Alt+Enter send  \u00b7  Alt+V attach image  \u00b7  :help  \u00b7  :q quit{img}"

    try:
        with patch_stdout():
            while True:
                try:
                    prompt_text = await session.prompt_async(
                        ANSI(f"{_GOLD}\u276f{_RESET} "),
                        bottom_toolbar=_toolbar,
                    )
                except (EOFError, KeyboardInterrupt):
                    _echo(f"\n{_GOLD}Farewell from the forge! \u2728{_RESET}")
                    break

                prompt_text = prompt_text.strip()

                if prompt_text.lower() in (":q", "quit", "exit"):
                    _echo(f"{_GOLD}Farewell from the forge! \u2728{_RESET}")
                    break

                # --- Command dispatch ---
                if prompt_text == ":help":
                    _show_help()
                    continue

                if prompt_text.startswith(":maidens"):
                    _parts = prompt_text.split(maxsplit=1)
                    if len(_parts) > 1:
                        _mname = _parts[1].strip().lower()
                        if _mname in _MAIDENS:
                            _echo("\n" + _maiden_card(_mname))
                        else:
                            _echo(
                                f"{_DIM}Unknown maiden: {_mname}. "
                                f"Try: {', '.join(_MAIDENS.keys())}{_RESET}"
                            )
                    else:
                        _echo(_maiden_gallery())
                    continue

                if prompt_text == ":status":
                    _echo(f"  {_GOLD}Agent:{_RESET}     {card.name} v{card.version}")
                    _echo(f"  {_GOLD}URL:{_RESET}       {agent}")
                    _echo(f"  {_GOLD}Context:{_RESET}   {context_id}")
                    _echo(f"  {_GOLD}Streaming:{_RESET} {card.capabilities.streaming}")
                    continue

                if prompt_text == ":copy":
                    if not _last_result:
                        _echo(f"{_DIM}Nothing to copy yet \u2014 run a command first.{_RESET}")
                    elif _copy_to_clipboard(_last_result):
                        _echo(f"{_GOLD_BRIGHT}\u2728 Copied to clipboard!{_RESET}")
                    else:
                        _echo(f"{_RED}Clipboard copy failed \u2014 try :save instead{_RESET}")
                    continue

                if prompt_text.startswith(":save"):
                    if not _last_result:
                        _echo(f"{_DIM}Nothing to save yet \u2014 run a command first.{_RESET}")
                        continue
                    parts_split = prompt_text.split(maxsplit=1)
                    filename = (
                        parts_split[1].strip() if len(parts_split) > 1 else "kourai_output.md"
                    )
                    try:
                        await AnyioPath(filename).write_text(_last_result, encoding="utf-8")
                        _echo(f"{_GOLD_BRIGHT}\u2728 Saved to {filename}{_RESET}")
                    except Exception as e:
                        _echo(f"{_RED}Save failed: {e}{_RESET}")
                    continue

                if prompt_text == ":clear":
                    click.clear()
                    continue

                if prompt_text.startswith(":"):
                    _echo(
                        f"{_DIM}Unknown command: {prompt_text} \u2014 "
                        "type :help for available commands{_RESET}"
                    )
                    continue

                if not prompt_text:
                    continue

                # Grab any images queued via Alt+V and clear the pending list
                attachments = pending_images.copy()
                pending_images.clear()

                _echo("")
                keep_going, context_id, _ = await send_and_stream(
                    client,
                    prompt_text,
                    context_id,
                    verbose=verbose,
                    attachments=attachments or None,
                )
                _echo("")

                if not keep_going:
                    _echo(f"{_GOLD}Farewell from the forge! \u2728{_RESET}")
                    break
    finally:
        if hasattr(client, "close"):
            await client.close()  # type: ignore[attr-defined]


if __name__ == "__main__":
    asyncio.run(main())
