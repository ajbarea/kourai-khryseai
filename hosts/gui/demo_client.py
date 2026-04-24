"""Scripted demo client for the GUI — for poster screenshots and recordings.

Replaces the real ``GuiClient`` with one that reacts to user input typed
into the real GUI input bar.  You type a prompt, the demo plays the
canned Hephaestus → Metis pause sequence so you can screenshot the
"Metis is waiting for input" moment.

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

if TYPE_CHECKING:
    import queue as _queue

logger = logging.getLogger(__name__)


# --- Canned response script ------------------------------------------------
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

# The Hephaestus → Metis handoff is generated automatically by
# queue_event_handler._maybe_handoff() when it sees the agent switch from
# hephaestus → metis in the stream, so we don't emit a manual "Metis!
# Draw up the plans..." line here (that would render it twice).  The
# built-in HANDOFF_LINES dict in hosts/gui/maidens.py has better variants.
_CSV_SEQUENCE: list[tuple[float, dict]] = [
    (
        1.0,
        {
            "type": "status",
            "text": "\U0001f4d0 analyzing events module...",
        },
    ),
    (
        0.9,
        {
            "type": "status",
            "text": "\U0001f4d0 found 3 models with datetime fields; nested "
            "relationships in Attendance and Session.",
        },
    ),
    (
        0.9,
        {
            "type": "status",
            "text": '\U0001f4d0 "One decision before I draft the spec."',
        },
    ),
    (
        1.0,
        {
            "type": "status",
            "text": '\U0001f4d0 INPUT_REQUIRED: "Should CSV export stream chunked I/O '
            "for large files? events.json has ~420k rows in production — "
            "loading all at once would spike memory. Streaming stays "
            'constant-memory but adds ~3ms/row of overhead."',
        },
    ),
]


def _matches_csv_prompt(text: str) -> bool:
    """Loose match — any phrasing around CSV export triggers the canned scene."""
    low = text.lower()
    return "csv" in low and ("export" in low or "stream" in low or "events" in low)


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
        # (target_agent, text) tuples from pygame_event_handler._submit_text.
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, self._send.get)
            if item is None:
                logger.info("DemoGuiClient shutdown signal received.")
                return

            # pygame_event_handler emits (target, text); other paths may
            # emit bare strings.  Tolerate both.
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
