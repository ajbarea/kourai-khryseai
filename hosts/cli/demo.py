"""Scripted demo mode for the CLI — for poster screenshots and recordings.

Plays a canned Hephaestus → Metis pipeline exchange that pauses at a
Metis clarifying question. Uses the exact same rendering primitives as
the real CLI, so the output is byte-identical to a real session.

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
    _BOLD,
    _DIM,
    _GOLD,
    _GOLD_BOLD,
    _ITALIC,
    _RESET,
)

# Soft magenta for ask/clarification lines — matches the poster palette.
_MAGENTA = "\033[38;2;242;106;140m"
_CYAN = "\033[38;2;125;224;224m"
_GREEN = "\033[38;2;125;216;132m"


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


async def run_demo(prompt_text: str | None = None) -> None:
    """Play the canned Hephaestus→Metis pause scene and wait for user input.

    The prompt will sit at the interactive `❯` cursor after the pipeline
    pauses, ready for a screenshot. Press Ctrl-C or answer y/n to exit.
    """
    demo_prompt = prompt_text or "implement CSV export with tests for the events module"

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

    # --- Hephaestus routes to Metis -------------------------------------------
    # Quoted + italic — Hephaestus is SPEAKING an in-character handoff line.
    _echo(
        f"🔥 {_GOLD_BOLD}Hephaestus{_RESET}: "
        f'{_ITALIC}"Metis! Draw up the plans. And no improvising."{_RESET}'
    )
    await _pause(0.8)

    # --- Metis streams analysis -----------------------------------------------
    # Unquoted — these are ACTIONS/STATUS (what Metis is doing), not speech.
    _echo("")
    _echo(f"📐 {_GOLD_BOLD}Metis{_RESET}: analyzing events module...")
    await _pause(0.45)
    _echo(f"   {_DIM}└─ found 3 models with datetime fields{_RESET}")
    await _pause(0.45)
    _echo(
        f"   {_DIM}└─ nested relationships in {_RESET}{_BOLD}Attendance{_RESET}"
        f"{_DIM} and {_RESET}{_BOLD}Session{_RESET}"
    )
    await _pause(0.65)

    # --- Metis pauses with clarifying question --------------------------------
    # Quoted + italic — Metis is SPEAKING to the player (transitional remark).
    _echo("")
    _echo(f'📐 {_GOLD_BOLD}Metis{_RESET}: {_ITALIC}"One decision before I draft the spec."{_RESET}')
    await _pause(0.3)
    _echo("")
    # The question itself is also speech — quoted + italic.  Magenta colour
    # still marks it as a clarifying/INPUT_REQUIRED line; the arrow is the
    # procedural cue.  The explanatory rationale below stays unquoted (it's
    # narrative context, not what Metis says out loud).
    _echo(
        f'   {_MAGENTA}→ {_ITALIC}"Should CSV export stream chunked I/O for large files?"{_RESET}'
    )
    _echo(f"     {_DIM}events.json has ~420k rows in prod. Loading all at once{_RESET}")
    _echo(f"     {_DIM}would spike memory. Streaming stays constant-memory.{_RESET}")
    await _pause(0.4)
    _echo("")
    _echo(
        f"     [{_GREEN}y{_RESET}] yes, stream chunked     [{_GREEN}n{_RESET}] no, load in memory"
    )
    _echo(f"     [{_CYAN}?{_RESET}] explain trade-offs      [{_MAGENTA}^C{_RESET}] cancel")
    _echo("")

    # --- Interactive prompt: waits for user. Exit cleanly on Ctrl-C / Ctrl-D. -
    # Use prompt_toolkit so the blinking cursor + styling match the real CLI.
    session: PromptSession[str] = PromptSession()
    prompt_str = ANSI(f"{_CYAN}❯{_RESET} ")
    try:
        with patch_stdout():
            answer = await session.prompt_async(prompt_str)
    except (EOFError, KeyboardInterrupt):
        _echo("")
        _echo(f"{_GOLD}Forge cooled. Farewell. ✨{_RESET}")
        return

    answer_clean = answer.strip().lower()
    _echo("")

    # Responses use the speech-vs-action rule: "Noted." is a spoken reply
    # (quoted + italic); the "drafting..." line that follows is status (plain).
    if answer_clean in {"y", "yes", "stream", "chunked"}:
        _echo(f'📐 {_GOLD_BOLD}Metis{_RESET}: {_ITALIC}"Noted."{_RESET}')
        _echo(f"📐 {_GOLD_BOLD}Metis{_RESET}: drafting spec with streaming I/O...")
        _echo(f"{_DIM}(demo stops here — this is where the real pipeline would resume.){_RESET}")
    elif answer_clean in {"n", "no", "memory"}:
        _echo(f'📐 {_GOLD_BOLD}Metis{_RESET}: {_ITALIC}"Noted."{_RESET}')
        _echo(f"📐 {_GOLD_BOLD}Metis{_RESET}: drafting spec with in-memory load...")
        _echo(f"{_DIM}(demo stops here — this is where the real pipeline would resume.){_RESET}")
    elif answer_clean in {"?", "help", "explain"}:
        _echo(
            f"📐 {_GOLD_BOLD}Metis{_RESET}: "
            f'{_ITALIC}"Streaming keeps memory flat but adds a small per-row cost. '
            f"Loading all at once is faster for files under ~100MB but scales "
            f"linearly with RAM — for events.json at 420k rows, streaming is "
            f'the right call."{_RESET}'
        )
        _echo(f"{_DIM}(demo exits after the explanation.){_RESET}")
    else:
        _echo(f"{_DIM}(demo exits — any real answer would resume the pipeline.){_RESET}")

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
