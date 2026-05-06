"""Scripted demo mode for the CLI — for poster screenshots and recordings.

Plays a canned Hephaestus → Metis pipeline exchange that pauses at a
Metis clarifying question. Uses the exact same rendering primitives as
the real CLI, so the output is byte-identical to a real session. The
beat list comes from ``kourai_common.demo_script`` so CLI and GUI agree
on the canonical scene; this module owns ANSI rendering only.

No network, no LLM — pure scripted output. Activated via `--demo` on
`make cli` or `python -m hosts.cli --demo`.

Invocation:
    python -m hosts.cli --demo
    KOURAI_DEMO_SLOW=1 python -m hosts.cli --demo   # slow mode for recording
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.patch_stdout import patch_stdout

from hosts.cli.rendering import _banner, _echo
from hosts.cli.styling import (
    _DIM,
    _GOLD,
    _GOLD_BOLD,
    _ITALIC,
    _RESET,
)
from kourai_common.demo_script import (
    CSV_DEMO_CHOICES,
    CSV_DEMO_TRIGGER,
    CSV_DEMO_TURNS,
    DemoTurn,
)

# Soft magenta for ask/clarification lines — matches the poster palette.
_MAGENTA = "\033[38;2;242;106;140m"
_CYAN = "\033[38;2;125;224;224m"
_GREEN = "\033[38;2;125;216;132m"

# Speaker → (emoji, display name) for the inline status header.
_SPEAKERS: dict[str, tuple[str, str]] = {
    "hephaestus": ("🔥", "Hephaestus"),
    "metis": ("📐", "Metis"),
}


# Default timing — gentle so screenshots can be taken mid-stream if wanted.
# Use KOURAI_DEMO_INSTANT=1 to skip all delays (best for a still screenshot).
# Use KOURAI_DEMO_SLOW=1 to slow everything to demo-recording speed.
def _pacing() -> float:
    if os.environ.get("KOURAI_DEMO_INSTANT"):
        return 0.0
    if os.environ.get("KOURAI_DEMO_SLOW"):
        return 1.6
    return 1.0


async def _pause(seconds: float) -> None:
    """Sleep scaled by the pacing multiplier — fast-forwarded when KOURAI_DEMO_INSTANT is set."""
    d = seconds * _pacing()
    if d > 0:
        await asyncio.sleep(d)


async def _pause_turn(turn: DemoTurn) -> None:
    """Wait the turn's pacing_ms (scaled), then yield."""
    await _pause(turn.pacing_ms / 1000.0)


def _render_turn(turn: DemoTurn, *, after_input_required: bool) -> None:
    """ANSI-render one canonical DemoTurn through ``_echo``.

    The ``after_input_required`` flag tracks rationale-line indentation:
    rationale beats following the question render as deeper-indented dim
    continuation lines beneath the question; rationale beats earlier in
    the stream render as the ``└─`` action sub-points beneath their
    parent action.
    """
    if turn.speaker not in _SPEAKERS:
        # Unknown speaker — skip. Defensive only; the canonical script
        # uses speakers from _SPEAKERS exclusively.
        return
    emoji, name = _SPEAKERS[turn.speaker]
    if turn.kind == "speech":
        _echo(f'{emoji} {_GOLD_BOLD}{name}{_RESET}: {_ITALIC}"{turn.text}"{_RESET}')
    elif turn.kind == "action":
        _echo("")
        _echo(f"{emoji} {_GOLD_BOLD}{name}{_RESET}: {turn.text}")
    elif turn.kind == "rationale" and not after_input_required:
        _echo(f"   {_DIM}└─ {turn.text}{_RESET}")
    elif turn.kind == "rationale":
        _echo(f"     {_DIM}{turn.text}{_RESET}")
    elif turn.kind == "input_required":
        _echo("")
        _echo(f'   {_MAGENTA}→ {_ITALIC}"{turn.text}"{_RESET}')


def _render_choice_menu() -> None:
    """Render the CSV-demo choice menu inline beneath the question."""
    by_key: dict[str, str] = {c.key: c.label for c in CSV_DEMO_CHOICES}
    yes_label = by_key.get("y", "yes")
    no_label = by_key.get("n", "no")
    explain_label = by_key.get("?", "explain")
    _echo("")
    _echo(f"     [{_GREEN}y{_RESET}] {yes_label}     [{_GREEN}n{_RESET}] {no_label}")
    _echo(f"     [{_CYAN}?{_RESET}] {explain_label}      [{_MAGENTA}^C{_RESET}] cancel")
    _echo("")


def _resolve_choice_key(answer: str) -> str | None:
    """Map a user reply to one of the canonical choice keys, else None."""
    cleaned = answer.strip().lower()
    if not cleaned:
        return None
    for choice in CSV_DEMO_CHOICES:
        if cleaned == choice.key or cleaned in choice.aliases:
            return choice.key
    return None


async def _render_response(key: str) -> None:
    """Render the response_turns for a chosen key."""
    choice = next((c for c in CSV_DEMO_CHOICES if c.key == key), None)
    if choice is None:
        return
    for turn in choice.response_turns:
        await _pause_turn(turn)
        _render_turn(turn, after_input_required=False)


async def run_demo(prompt_text: str | None = None) -> None:
    """Play the canned Hephaestus → Metis pause scene and wait for user input.

    The prompt sits at the interactive `❯` cursor after the pipeline
    pauses, ready for a screenshot. Press Ctrl-C or answer y/n to exit.
    """
    demo_prompt = prompt_text or CSV_DEMO_TRIGGER

    # --- Banner / welcome (mirrors the real CLI) ------------------------------
    _echo(_banner())
    _echo(
        f"{_DIM}Connected to {_GOLD}Hephaestus{_RESET}{_DIM} v0.9.2 "
        f"· 10 agents online · forge warm{_RESET}"
    )
    _echo(f"{_DIM}Model: {_GOLD}claude-opus-4-7{_DIM} · demo mode (no network, no LLM){_RESET}")
    _echo("")
    await _pause(0.4)

    # --- User's "typed" prompt (rendered as though already entered) -----------
    _echo(f"{_CYAN}❯{_RESET} {demo_prompt}")
    _echo("")
    await _pause(0.5)

    # --- Walk the canonical turn list ----------------------------------------
    seen_input_required = False
    for turn in CSV_DEMO_TURNS:
        await _pause_turn(turn)
        _render_turn(turn, after_input_required=seen_input_required)
        if turn.kind == "input_required":
            seen_input_required = True
    await _pause(0.4)
    _render_choice_menu()

    # --- Interactive prompt: waits for user. Exit cleanly on Ctrl-C / Ctrl-D. -
    session: PromptSession[str] = PromptSession()
    prompt_str = ANSI(f"{_CYAN}❯{_RESET} ")
    try:
        with patch_stdout():
            answer = await session.prompt_async(prompt_str)
    except (EOFError, KeyboardInterrupt):
        _echo("")
        _echo(f"{_GOLD}Forge cooled. Farewell. ✨{_RESET}")
        return

    _echo("")
    key = _resolve_choice_key(answer)
    if key is None:
        _echo(f"{_DIM}(demo exits — any real answer would resume the pipeline.){_RESET}")
        _echo("")
        return
    await _render_response(key)
    if key in {"y", "n"}:
        _echo(f"{_DIM}(demo stops here — this is where the real pipeline would resume.){_RESET}")
    elif key == "?":
        _echo(f"{_DIM}(demo exits after the explanation.){_RESET}")
    _echo("")


def main() -> None:
    """Entry point when invoked as `python -m hosts.cli.demo`."""
    # Windows UTF-8 handling mirrors hosts/cli/__main__.py for emoji + box-drawing
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io as _io

        sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run_demo())


if __name__ == "__main__":
    main()
