"""Visual rendering — PNG-to-ANSI art, markdown, comms windows, cards, banner.

All functions that produce formatted terminal output live here.
"""

from __future__ import annotations

import re
import secrets
import shutil
import sys
import textwrap
from datetime import datetime
from typing import IO, TYPE_CHECKING, Any

from hosts.cli.maidens import (
    _ASSETS_DIR,
    _MAIDENS,
    _TAGLINES,
)
from hosts.cli.styling import (
    _BOLD,
    _DIM,
    _GOLD,
    _GOLD_BOLD,
    _GOLD_BRIGHT,
    _ITALIC,
    _RESET,
    agent_badge,
)
from kourai_common.ssml import strip_ssml

if TYPE_CHECKING:
    from pathlib import Path

# Save a reference to the real stdout BEFORE prompt_toolkit's patch_stdout
# can wrap it.  Dense ANSI (pixel art, true-color) gets mangled by
# prompt_toolkit's VT parser on Windows — writing to the real stdout
# bypasses that entirely.  Safe because we only _echo() between prompts,
# never while the prompt is being displayed.
_raw_out: IO[str] = sys.stdout


def set_raw_out(stream: IO[str]) -> None:
    """Replace the raw output stream (call before patch_stdout wraps sys.stdout)."""
    global _raw_out
    _raw_out = stream


# ---------------------------------------------------------------------------
# Image-to-terminal renderer — turns PNG/JPG into beautiful ANSI pixel art
# Uses Unicode half-blocks (▀) with true-color for 2 vertical pixels per char.
# Think: mecha anime comms window showing pilot faces in golden frames.
# ---------------------------------------------------------------------------


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

    # Warm amber gold for tinting — matches docs gold-mid (#C9944A)
    gold_r, gold_g, gold_b = 201, 148, 74

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
    # M18 Phase 2: SSML may arrive from any producer (HEPH_HANDOFFS,
    # HANDOFF_LINES, VICTORY_LINES, future LLM-generated SSML). Strip
    # at the display chokepoint so every caller of _comms_window gets
    # clean text without remembering to strip first. strip_ssml is
    # idempotent and fast on plain text (early return on no `<`).
    dialogue = strip_ssml(dialogue)

    m = _MAIDENS.get(agent_name)
    if not m:
        return f"  {_DIM}[{agent_name}] {dialogue}{_RESET}"

    title = str(m["title"])

    # Speech-vs-action: per the agents-speak-don't-emit guiding principle,
    # a line that starts with a double-quote is dialogue (the maiden talking
    # to the player) and renders italic; an unquoted line is a status report
    # and stays plain. The convention is uniform across CLI/GUI/VN so the
    # human-on-the-loop checkpoint pops against the status stream.
    is_dialogue = dialogue.lstrip().startswith('"')

    # Style variants
    if style == "shout":
        text_col = _GOLD_BRIGHT
        border = _GOLD_BOLD
        dialogue = dialogue.upper()
    elif style == "whisper":
        text_col = f"{_DIM}{_ITALIC}" if is_dialogue else _DIM
        border = _DIM
    else:
        text_col = _ITALIC if is_dialogue else _RESET
        border = _GOLD

    # Dynamic width detection
    term_w, _ = shutil.get_terminal_size((80, 24))
    # Leave room for left margin (2) + border (1) + padding (1) + right padding (1) + border (1)
    max_w = min(120, term_w - 8)

    # Wrap dialogue lines
    wrapped_lines = textwrap.wrap(dialogue, width=max_w)
    if not wrapped_lines:
        wrapped_lines = [""]

    # Box width is the longest line length
    box_w = max(len(line) for line in wrapped_lines)
    # Ensure header (timestamp + " NAME " badge + " — " + title) fits.
    # The badge wraps the name in one space on each side so the colored
    # background reads as a chip — that's +2 visible chars over the bare
    # name length the legacy ``_GOLD_BOLD`` rendering occupied.
    ts_prefix = f"[{datetime.now().strftime('%H:%M:%S')}] "
    header_len = len(ts_prefix) + len(agent_name) + 2 + len(title) + 3
    box_w = max(box_w, header_len)

    # Final clamping to terminal width
    box_w = min(box_w, max_w)

    top_bar = "\u2500" * (box_w + 2)
    bot_bar = "\u2500" * (box_w + 2)

    output = []
    output.append(f"  {border}\u256d{top_bar}\u256e{_RESET}")
    output.append(
        f"  {border}\u2502{_RESET} {_DIM}{ts_prefix}{_RESET}{agent_badge(agent_name)} \u2014 {_DIM}{title}{_RESET}{' ' * (box_w - header_len + 1)}{border}\u2502{_RESET}"
    )

    for line in wrapped_lines:
        padding = " " * (box_w - len(line) + 1)
        output.append(
            f"  {border}\u2502{_RESET} {text_col}{line}{_RESET}{padding}{border}\u2502{_RESET}"
        )

    output.append(f"  {border}\u2570{bot_bar}\u256f{_RESET}")

    return "\n".join(output)


def _maiden_card(name: str) -> str:
    """Render a golden maiden's portrait card with art and a sassy quote."""
    m = _MAIDENS.get(name)
    if not m:
        return f"{_DIM}Unknown maiden: {name}{_RESET}"

    # M18 Phase 2: AGENT_QUOTES are SSML; strip for the maiden card display.
    quote = strip_ssml(secrets.choice(m["quotes"])) if m.get("quotes") else ""

    # Load avatar (PNG/JPG anime portrait > kaomoji fallback)
    raw_art = _get_maiden_art(name, str(m["face"]), size="card")
    art_lines = raw_art.split("\n")
    art_section = "\n".join(f"  {_GOLD}\u2503{_RESET}  {line}" for line in art_lines)

    return (
        f"  {_GOLD}\u250f\u2501\u2501\u2501 \u2726 {_GOLD_BOLD}{name.upper()}{_RESET}{_GOLD} \u2726"
        f" \u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501{_RESET}\n"
        f"  {_GOLD}\u2503{_RESET}  {m['title']}\n"
        f"  {_GOLD}\u2503{_RESET}  {_DIM}{m['desc']}{_RESET}\n"
        f"  {_GOLD}\u2503{_RESET}\n"
        f"{art_section}\n"
        f"  {_GOLD}\u2503{_RESET}\n"
        + (f'  {_GOLD}\u2503{_RESET}  {_ITALIC}"{quote}"{_RESET}\n' if quote else "")
        + f"  {_GOLD}\u2517\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501{_RESET}"
    )


def _maiden_gallery() -> str:
    """Render all golden maidens in a gallery display."""
    header = (
        f"\n{_GOLD_BOLD}  \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550{_RESET}\n"
        f"{_GOLD_BOLD}    \u2726  THE GOLDEN MAIDENS  \u2726{_RESET}\n"
        f"{_GOLD_BOLD}  \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550{_RESET}\n"
        f"  {_DIM}Kourai Khryseai \u2014 Hephaestus' divine automata{_RESET}\n"
        f"  {_DIM}Avatars: docs/assets/maidens/golden_avatars/<name>.png{_RESET}\n"
    )
    cards = "\n\n".join(_maiden_card(name) for name in _MAIDENS)
    return header + "\n" + cards


def _banner() -> str:
    tagline = secrets.choice(_TAGLINES)
    term_w, _ = shutil.get_terminal_size((80, 24))

    title_text = "Kourai Khryseai \u2014 Golden Maidens"
    # ``banner_w`` is the *interior* width \u2014 the space between the two \u2502 bars.
    # Top/bottom bars and the title row must all render to exactly banner_w
    # columns so the rounded box is a clean rectangle.
    #   min 44 to fit title, max 80 for reasonable banner size.
    banner_w = max(44, min(80, term_w - 8))

    top_bar = "\u2500" * banner_w

    # Centre the title inside banner_w columns \u2014 no extra wrapper spaces.
    # (The old formula wrapped title_row in ` ... ` which made it banner_w + 2
    # columns wide, so the right bar always drifted 2 columns past the corner.)
    title_len = len(title_text)
    left_pad = max(0, (banner_w - title_len) // 2)
    right_pad = max(0, banner_w - title_len - left_pad)
    title_row = f"{' ' * left_pad}{title_text}{' ' * right_pad}"

    return (
        f"{_GOLD_BOLD}\u256d{top_bar}\u256e{_RESET}\n"
        f"{_GOLD_BOLD}\u2502{title_row}\u2502{_RESET}\n"
        f"{_GOLD_BOLD}\u2570{top_bar}\u256f{_RESET}\n"
        f"{_DIM}{_ITALIC}{tagline}{_RESET}\n"
        f"\n"
        f"{_GOLD}Enter{_RESET} send  \u00b7  {_GOLD}Ctrl+V{_RESET} paste  \u00b7  "
        f"{_GOLD}Alt+V{_RESET} attach image\n"
        f"{_GOLD}/help{_RESET} commands  \u00b7  {_GOLD}/q{_RESET} quit\n"
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

    term_w, _ = shutil.get_terminal_size((80, 24))
    bar_w = min(100, term_w - 4)

    for line in lines:
        # Code block fences
        if line.strip().startswith("```"):
            if in_code_block:
                in_code_block = False
                rendered.append(f"{_DIM}{'\u2500' * bar_w}{_RESET}")
            else:
                in_code_block = True
                lang = line.strip().removeprefix("```").strip()
                if lang:
                    rendered.append(
                        f"{_DIM}\u2500\u2500\u2500 {lang} "
                        f"{'\u2500' * max(1, bar_w - len(lang) - 5)}{_RESET}"
                    )
                else:
                    rendered.append(f"{_DIM}{'\u2500' * bar_w}{_RESET}")
            continue

        if in_code_block:
            rendered.append(f"  {_DIM}{line}{_RESET}")
            continue

        # Horizontal rules
        if re.match(r"^-{3,}\s*$", line.strip()):
            rendered.append(f"{_GOLD}{'\u2501' * bar_w}{_RESET}")
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
        import asyncclick as click

        click.echo(text)


def _clear_screen() -> None:
    """Clear the terminal viewport (matches Ubuntu's `clear`).

    Writes the cursor-home + erase-screen sequence directly to _raw_out so
    the ESC byte survives prompt_toolkit's patch_stdout (which sanitizes \\x1b
    to '?' and turns click.clear() output into literal '?[2J?[1;1H').
    """
    try:
        _raw_out.write("\x1b[H\x1b[2J")
        _raw_out.flush()
    except Exception:
        import asyncclick as click

        click.clear()
