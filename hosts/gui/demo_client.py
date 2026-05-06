"""Scripted demo client for the GUI — for poster screenshots and recordings.

Replaces the real ``GuiClient`` with one that reacts to user input typed
into the real GUI input bar.  You type a prompt, the demo plays the
canned Hephaestus → Metis pause sequence so you can screenshot the
"Metis is waiting for input" moment.

The beat list comes from ``kourai_common.demo_script`` so CLI and GUI
agree on the canonical scene; this module owns the recv-queue event
shape only.

Activated via ``--demo`` on ``make gui-demo`` / ``python -m hosts.gui --demo``.
No network, no LLM, no A2A.

Usage:
    make gui-demo
    (type any of the trigger prompts below — default: "implement csv export")
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import TYPE_CHECKING

from kourai_common.demo_script import (
    CSV_DEMO_TURNS,
    DemoTurn,
    matches_csv_trigger,
)

if TYPE_CHECKING:
    import queue as _queue

logger = logging.getLogger(__name__)


# --- Canonical script → recv-queue event sequence -------------------------
# Emoji prefixes route through GUI's detect_agent (hosts/gui/maidens.py)
# and trigger portrait flips + name-card updates automatically.
#
# Dialogue convention (ROADMAP M10 "Agents speak, don't emit"):
#   * Agent SPEECH → wrapped in "..." for the downstream italic pass.
#   * Agent ACTION / STATUS → plain prose after the emoji prefix.
#   * INPUT_REQUIRED: prefix routes through _handle_input_required,
#     setting input_bar.waiting_for_agent to the speaking agent — which
#     is exactly what makes the "Metis is waiting for input" framing
#     work for the poster screenshot.
#
# The Hephaestus → Metis handoff is generated automatically by
# queue_event_handler._maybe_handoff() when it sees the agent switch from
# hephaestus → metis in the stream, so we skip Hephaestus's speech turn
# from CSV_DEMO_TURNS — the built-in HANDOFF_LINES has better variants.

_SPEAKER_EMOJI: dict[str, str] = {
    "hephaestus": "\U0001f525",  # 🔥
    "metis": "\U0001f4d0",  # 📐
}


def _format_event(turn: DemoTurn, *, pending_rationale: list[str]) -> dict | None:
    """Translate one canonical turn into a recv-queue status event.

    Returns ``None`` for turns that should be folded into a later event
    (rationale lines following an action / input_required get bundled).
    """
    if turn.kind == "rationale":
        pending_rationale.append(turn.text)
        return None
    emoji = _SPEAKER_EMOJI.get(turn.speaker, "")
    if turn.kind == "speech":
        return {"type": "status", "text": f'{emoji} "{turn.text}"'}
    if turn.kind == "action":
        # Flush queued rationale into the previous emit's tail; for the
        # opening "analyzing events module..." action there's nothing
        # pending yet, so this is a clean status line.
        text = turn.text
        if pending_rationale:
            text = f"{text} {'; '.join(pending_rationale)}"
            pending_rationale.clear()
        return {"type": "status", "text": f"{emoji} {text}"}
    if turn.kind == "input_required":
        text = turn.text
        if pending_rationale:
            text = f"{text} {' '.join(pending_rationale)}"
            pending_rationale.clear()
        return {"type": "status", "text": f'{emoji} INPUT_REQUIRED: "{text}"'}
    return None


def _build_csv_sequence() -> list[tuple[float, dict]]:
    """Materialize CSV_DEMO_TURNS into the recv-queue event list.

    Hephaestus's opening speech is dropped because the GUI's
    queue_event_handler._maybe_handoff synthesizes a richer handoff line
    when it sees the agent switch.

    Rationale beats following a non-rationale beat get bundled into that
    beat's text — the GUI's dialogue panel renders one status per emit
    and we don't want sub-points becoming disconnected entries.
    """
    out: list[tuple[float, dict]] = []
    pending: list[str] = []
    for turn in CSV_DEMO_TURNS:
        if turn.speaker == "hephaestus" and turn.kind == "speech":
            continue
        event = _format_event(turn, pending_rationale=pending)
        if event is not None:
            out.append((turn.pacing_ms / 1000.0, event))
        elif out and pending:
            # Rationale that landed AFTER an emitted event — fold into
            # that event's text and re-emit. Preserves the "include the
            # rationale prose" intent without adding a separate row.
            last_delay, last_event = out[-1]
            updated_text = f"{last_event['text']} {'; '.join(pending)}"
            out[-1] = (last_delay, {**last_event, "text": updated_text})
            pending.clear()
    # Trailing rationale (no further event to merge into) gets its own
    # final status line.
    if pending:
        emoji = _SPEAKER_EMOJI.get("metis", "")
        out.append(
            (0.4, {"type": "status", "text": f"{emoji} {' '.join(pending)}"}),
        )
    return out


_CSV_SEQUENCE: list[tuple[float, dict]] = _build_csv_sequence()


def _matches_csv_prompt(text: str) -> bool:
    """Loose match — any phrasing around CSV export triggers the canned scene."""
    return matches_csv_trigger(text)


class DemoGuiClient:
    """Drop-in replacement for ``GuiClient`` that reacts to typed input.

    Matches the real client's constructor signature (send_q, recv_q,
    agent_url) so the subsystem loader can swap it in without any other
    plumbing changes.

    Flow per turn:
      1. Player types a prompt into the real GUI input bar.
      2. pygame_event_handler puts ``(target_agent, text)`` on send_q.
      3. We match the text against known triggers and drive a scripted
         sequence of status events into recv_q.
      4. The GUI renders each event through its normal pipeline —
         portraits flip, dialogue history typewriter-renders, the input
         bar flips to "waiting for Metis".
    """

    def __init__(
        self,
        send_q: _queue.Queue,
        recv_q: _queue.Queue,
        agent_url: str | None = None,
    ) -> None:
        self._send = send_q
        self._recv = recv_q
        self._current_agent = "hephaestus"

    async def run(self) -> None:
        """Emit the initial greeting, then loop on send_q forever."""
        logger.info("DemoGuiClient.run() — scripted demo mode, no network.")

        # Fake handshake so the built-in "The forge is hot. What are we
        # building?" greeting from queue_event_handler._handle_connected
        # renders.  No tutorial line — Hephaestus doesn't break character
        # to tell the player what to type.
        self._recv.put_nowait({"type": "connected", "name": "Hephaestus (demo mode)"})

        # React to each prompt the player types.  Items on send_q are
        # (target_agent, text, attachments) 3-tuples from
        # pygame_event_handler._submit_text (M11). The legacy 2-tuple shape
        # is still tolerated so a non-GUI caller can wire a bare prompt
        # without learning the new slot. Demo mode silently discards any
        # attachments — no agent is on the other end to consume them.
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, self._send.get)
            if item is None:
                logger.info("DemoGuiClient shutdown signal received.")
                return

            if isinstance(item, tuple) and len(item) >= 2:
                _target, user_text = item[0], item[1]
            else:
                user_text = str(item)

            threading.Thread(
                target=self._respond,
                args=(user_text,),
                daemon=True,
            ).start()

    # ------------------------------------------------------------------
    def _respond(self, user_text: str) -> None:
        """Pick a canned response for the typed prompt and stream it."""
        try:
            if _matches_csv_prompt(user_text):
                logger.debug("Demo: matched CSV-export prompt.")
                self._stream_sequence(_CSV_SEQUENCE)
                return

            # Unknown prompt — release the input bar silently without
            # forcing Hephaestus to break character.  Operator docs live
            # in the README / Makefile help, not in-world dialogue.
            logger.info("Demo: prompt %r did not match any scene; ignoring.", user_text)
            self._recv.put_nowait({"type": "complete", "elapsed": 0.1})
        except Exception:
            logger.exception("Demo responder crashed")

    def _stream_sequence(self, seq: list[tuple[float, dict]]) -> None:
        """Push the given canned event list onto recv_q with pacing."""
        for delay, event in seq:
            time.sleep(delay)
            logger.debug("demo event: %s", event.get("type"))
            self._recv.put_nowait(event)
        # Note: no "complete" event — the final event is INPUT_REQUIRED,
        # which leaves the input bar in "waiting for Metis" state.  That's
        # the screenshot moment.  Typing again will re-trigger the scene.
