"""Canonical CSV-export demo script — Hephaestus → Metis pause scene.

Pre-this-module the same scripted scene was hand-coded three times:
``hosts/cli/demo.py`` rendered ANSI ``_echo`` lines, ``hosts/gui/demo_client.py``
pushed status events onto a recv-queue, and ``hosts/vn/kourai_vn/game/
script_poster_demo.rpy`` ran Ren'Py labels — same beats, three encodings.
This module owns the dialogue beats, choice keys, and answer responses;
CLI and GUI iterate the shared lists and render in their own primitives.
The Ren'Py file can't cleanly import Python at script-time, so it stays
hand-coded with a header comment cross-referencing this file as the
canonical source.

Schema: each ``DemoTurn`` carries WHO speaks (``speaker``), the INTENT
of the line (``kind``), the canonical TEXT, and a ``pacing_ms`` hint.
Hosts decide the rendering: CLI italicizes ``speech`` and dim-prefixes
``action``; GUI routes through its emoji-prefix detector and dialogue
panel. ``rationale`` continuation lines are sub-points the CLI shows
beneath an ``input_required`` and the GUI bundles into the same status
line.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DemoTurn:
    """One beat in the canned scene."""

    speaker: str  # "hephaestus" | "metis" | "user"
    kind: str  # "speech" | "action" | "rationale" | "input_required"
    text: str
    pacing_ms: int = 800  # delay before this turn renders (relative to previous)


@dataclass(frozen=True)
class DemoChoice:
    """One pickable answer at the ``input_required`` beat."""

    key: str  # short keypress: "y" / "n" / "?"
    label: str  # menu label shown to the player
    aliases: frozenset[str] = field(default_factory=frozenset)
    response_turns: tuple[DemoTurn, ...] = ()


# --- Trigger phrase used by both hosts to open the demo --------------------

CSV_DEMO_TRIGGER: str = "implement CSV export with tests for the events module"


def matches_csv_trigger(text: str) -> bool:
    """Loose match — any phrasing about CSV export triggers the canned scene."""
    low = text.lower()
    return "csv" in low and ("export" in low or "stream" in low or "events" in low)


# --- Canonical turn sequence ------------------------------------------------

CSV_DEMO_TURNS: list[DemoTurn] = [
    DemoTurn(
        speaker="hephaestus",
        kind="speech",
        text="Metis! Draw up the plans. And no improvising.",
        pacing_ms=500,
    ),
    DemoTurn(
        speaker="metis",
        kind="action",
        text="analyzing events module...",
        pacing_ms=800,
    ),
    DemoTurn(
        speaker="metis",
        kind="rationale",
        text="found 3 models with datetime fields",
        pacing_ms=450,
    ),
    DemoTurn(
        speaker="metis",
        kind="rationale",
        text="nested relationships in Attendance and Session",
        pacing_ms=450,
    ),
    DemoTurn(
        speaker="metis",
        kind="speech",
        text="One decision before I draft the spec.",
        pacing_ms=650,
    ),
    DemoTurn(
        speaker="metis",
        kind="input_required",
        text="Should CSV export stream chunked I/O for large files?",
        pacing_ms=300,
    ),
    DemoTurn(
        speaker="metis",
        kind="rationale",
        text=(
            "events.json has ~420k rows in production — loading all at once "
            "would spike memory. Streaming stays constant-memory but adds "
            "~3ms/row of overhead."
        ),
        pacing_ms=400,
    ),
]


# --- Player choices at the input_required beat -----------------------------

CSV_DEMO_CHOICES: list[DemoChoice] = [
    DemoChoice(
        key="y",
        label="yes, stream chunked",
        aliases=frozenset({"yes", "stream", "chunked"}),
        response_turns=(
            DemoTurn(speaker="metis", kind="speech", text="Noted.", pacing_ms=200),
            DemoTurn(
                speaker="metis",
                kind="action",
                text="drafting spec with streaming I/O...",
                pacing_ms=300,
            ),
        ),
    ),
    DemoChoice(
        key="n",
        label="no, load in memory",
        aliases=frozenset({"no", "memory"}),
        response_turns=(
            DemoTurn(speaker="metis", kind="speech", text="Noted.", pacing_ms=200),
            DemoTurn(
                speaker="metis",
                kind="action",
                text="drafting spec with in-memory load...",
                pacing_ms=300,
            ),
        ),
    ),
    DemoChoice(
        key="?",
        label="explain trade-offs",
        aliases=frozenset({"help", "explain"}),
        response_turns=(
            DemoTurn(
                speaker="metis",
                kind="speech",
                text=(
                    "Streaming keeps memory flat but adds a small per-row cost. "
                    "Loading all at once is faster for files under ~100MB but "
                    "scales linearly with RAM — for events.json at 420k rows, "
                    "streaming is the right call."
                ),
                pacing_ms=200,
            ),
        ),
    ),
]


__all__ = [
    "CSV_DEMO_CHOICES",
    "CSV_DEMO_TRIGGER",
    "CSV_DEMO_TURNS",
    "DemoChoice",
    "DemoTurn",
    "matches_csv_trigger",
]
