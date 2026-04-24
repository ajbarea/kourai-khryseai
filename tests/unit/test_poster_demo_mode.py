"""Smoke tests for the scripted demo paths — CLI and GUI.

These exist to catch drift when the real client/rendering shapes change
without anyone touching the demo harness (which is easy to forget,
since demo mode is an explicit opt-in flag).  They do NOT verify agent
semantics — just that the canned script still produces the events and
output a screenshot-workflow would rely on.
"""

from __future__ import annotations

import queue as _queue
import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from hosts.gui.demo_client import DemoGuiClient
    from hosts.gui.dialogue import DialogueEntry

# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------


class TestCliDemoImports:
    """The CLI demo module must import without touching a real Hephaestus URL."""

    def test_module_imports_clean(self) -> None:
        from hosts.cli import demo  # noqa: F401

    def test_run_demo_is_async(self) -> None:
        import asyncio

        from hosts.cli.demo import run_demo

        assert asyncio.iscoroutinefunction(run_demo)

    def test_main_entry_symbol_exists(self) -> None:
        from hosts.cli.demo import main

        assert callable(main)


# ---------------------------------------------------------------------------
# GUI demo — the interesting one
# ---------------------------------------------------------------------------


class TestGuiDemoClientScriptedSequence:
    """DemoGuiClient must emit the canned CSV-export scene verbatim.

    The real screenshot workflow hinges on exactly these events reaching
    the dialogue/portrait/input-bar subsystems.  If the shape drifts and
    no one notices, ``make gui-demo`` silently renders the wrong scene.
    """

    def _fresh_client(self) -> tuple[_queue.Queue, _queue.Queue, DemoGuiClient]:
        from hosts.gui.demo_client import DemoGuiClient

        send_q: _queue.Queue = _queue.Queue()
        recv_q: _queue.Queue = _queue.Queue()
        return send_q, recv_q, DemoGuiClient(send_q, recv_q)

    def _drain(self, q: _queue.Queue, deadline_s: float = 8.0) -> list[dict]:
        """Collect every event on `q` until it goes quiet for 0.5s."""
        out: list[dict] = []
        end = time.monotonic() + deadline_s
        while time.monotonic() < end:
            try:
                out.append(q.get(timeout=0.5))
            except _queue.Empty:
                if out:  # we got something and nothing else for 0.5s
                    break
        return out

    def test_csv_prompt_triggers_full_sequence(self) -> None:
        """Full scene: metis analysis → speech → clarifying question.

        The demo_client emits only the Metis events (📐) — the Hephaestus
        handoff line (🔥) is injected by the GUI's
        ``_maybe_handoff`` at render time when queue_event_handler sees
        the agent switch.  So we assert on what the demo actually puts on
        the queue, not on what the rendered dialogue history shows.
        """
        send_q, recv_q, client = self._fresh_client()

        # _respond is the sync entry point that _run threads into.  Calling
        # it directly avoids spinning up asyncio just for a smoke test.
        client._respond("implement CSV export with tests for the events module")

        events = self._drain(recv_q)
        texts = [e.get("text", "") for e in events if e.get("type") == "status"]

        # Metis begins working (action — no quotes, emoji prefix flips portrait)
        assert any(t.startswith("\U0001f4d0") and "analyzing events module" in t for t in texts), (
            f"missing Metis analysis in {texts!r}"
        )

        # Metis speech (quoted — the M10 speech-vs-action convention)
        speech_lines = [t for t in texts if '"' in t]
        assert any("One decision before I draft the spec" in t for t in speech_lines), (
            f"missing Metis transitional speech in {speech_lines!r}"
        )

        # The clarifying question routes through _handle_input_required
        # by carrying INPUT_REQUIRED: in the status text.  That's what flips
        # the input bar to 'Metis is waiting for input' — the screenshot
        # moment.
        assert any("INPUT_REQUIRED:" in t for t in texts), (
            f"missing INPUT_REQUIRED marker in {texts!r}"
        )

        # Every status event should start with Metis's emoji — nothing
        # on this queue should be a Hephaestus line, because auto-handoff
        # owns that.  Guards against accidentally re-adding a duplicate
        # handoff from the demo script itself (earlier bug).
        for t in texts:
            assert t.startswith("\U0001f4d0"), (
                f"demo_client emitted a non-Metis status (duplicate handoff risk): {t!r}"
            )

    def test_unknown_prompt_releases_input_bar(self) -> None:
        """A miss shouldn't leave the GUI stuck in processing state."""
        send_q, recv_q, client = self._fresh_client()
        client._respond("hello there")  # does not match the CSV matcher

        events = self._drain(recv_q, deadline_s=2.0)

        # Unknown prompts emit a `complete` event and nothing else.  No
        # Hephaestus tutorial dialogue should leak into the history.
        types = [e.get("type") for e in events]
        assert "complete" in types, f"no complete event on unknown prompt: {types}"

        # Crucial: no meta-instruction dialogue.  (An earlier iteration
        # had Hephaestus say 'type implement CSV export…' which ruined
        # screenshots.)
        for e in events:
            text = e.get("text", "")
            assert "implement CSV export" not in text, (
                f"meta-instruction leaked into unknown-prompt path: {text!r}"
            )

    def test_matcher_is_forgiving(self) -> None:
        """The matcher should accept common phrasings around 'csv export'."""
        from hosts.gui.demo_client import _matches_csv_prompt

        yes = [
            "implement CSV export with tests for the events module",
            "add csv export with tests",
            "CSV EXPORT please",
            "stream csv events",
            "implement csv for events",
        ]
        no = [
            "",
            "hello",
            "write some tests",
            "plan something",
        ]
        for prompt in yes:
            assert _matches_csv_prompt(prompt), f"matcher missed {prompt!r}"
        for prompt in no:
            assert not _matches_csv_prompt(prompt), f"matcher overshot on {prompt!r}"


class TestGuiDemoClientShape:
    """Signature parity with the real GuiClient.

    subsystem_loader.py swaps one for the other based on `demo_mode` —
    they must accept identical constructor args and expose a callable
    `run` coroutine.
    """

    def test_constructor_accepts_same_args_as_real_client(self) -> None:
        from hosts.gui.client import GuiClient
        from hosts.gui.demo_client import DemoGuiClient

        send_q: _queue.Queue = _queue.Queue()
        recv_q: _queue.Queue = _queue.Queue()

        # Both should accept (send_q, recv_q, agent_url).
        real = GuiClient(send_q, recv_q, None)
        demo = DemoGuiClient(send_q, recv_q, None)
        assert real is not None
        assert demo is not None

    def test_run_is_async(self) -> None:
        import asyncio

        from hosts.gui.demo_client import DemoGuiClient

        assert asyncio.iscoroutinefunction(DemoGuiClient.run)


class TestUserEventHandler:
    """`type: user` events should land as user-attributed dialogue entries.

    The demo client uses this to paint a user prompt in the history.
    The real A2A client never emits it (pygame_event_handler injects user
    text directly on TEXTINPUT) — so this path is screenshot-mode only,
    but when it's used it must produce an is_user=True entry.
    """

    def test_user_event_appends_user_dialogue_entry(self) -> None:
        from unittest.mock import MagicMock

        from hosts.gui.queue_event_handler import QueueEventHandler

        # Minimal mocks — _handle_user only touches self.history.
        history = MagicMock()
        added: list[DialogueEntry] = []
        history.add.side_effect = lambda e: added.append(e)

        handler = QueueEventHandler(
            state=MagicMock(),
            history=history,
            portrait=MagicMock(),
            input_bar=MagicMock(),
            typewriter=MagicMock(),
            flash=MagicMock(),
            tts_manager=MagicMock(),
            gui_integration=MagicMock(),
            audio_manager=MagicMock(),
            debug_log=MagicMock(),
        )

        handler.process_event({"type": "user", "text": "implement CSV export"})

        assert len(added) == 1
        entry = added[0]
        assert entry.agent == "user"
        assert entry.is_user is True
        assert "CSV export" in entry.text

    def test_empty_user_event_is_ignored(self) -> None:
        from unittest.mock import MagicMock

        from hosts.gui.queue_event_handler import QueueEventHandler

        history = MagicMock()
        handler = QueueEventHandler(
            state=MagicMock(),
            history=history,
            portrait=MagicMock(),
            input_bar=MagicMock(),
            typewriter=MagicMock(),
            flash=MagicMock(),
            tts_manager=MagicMock(),
            gui_integration=MagicMock(),
            audio_manager=MagicMock(),
            debug_log=MagicMock(),
        )

        handler.process_event({"type": "user", "text": ""})
        assert history.add.call_count == 0


# ---------------------------------------------------------------------------
# Font scale registry — invalidation contract for zoom
# ---------------------------------------------------------------------------


class TestFontScaleRegistry:
    """The FontProxy registry must invalidate every proxy when scale changes."""

    def test_set_font_scale_invalidates_cached_fonts(self) -> None:
        import pygame

        from hosts.gui import constants

        # Drive-by init: pygame.freetype requires pygame.init() in some envs.
        pygame.init()
        try:
            # Force every proxy to cache a font at the current scale.
            _ = constants.FONT_BODY.path
            _ = constants.FONT_NAME.path
            [p._rendered_size for p in constants._font_proxy_registry]

            constants.set_font_scale(1.5)
            # Caches should be dropped; _rendered_size reflects stale size
            # but _font is None, so the next access rebuilds.
            dropped = [p._font is None for p in constants._font_proxy_registry]
            assert all(dropped), "some FontProxy instances were not invalidated"

            # Trigger rebuild on one proxy to prove the new size bakes in.
            _ = constants.FONT_BODY.path
            assert constants.FONT_BODY._rendered_size > 0
            assert constants.FONT_BODY._rendered_size != 0

            # Restore to keep other tests deterministic.
            constants.set_font_scale(1.0)
        finally:
            pygame.quit()

    def test_scale_change_no_op_when_identical(self) -> None:
        from hosts.gui import constants

        constants.set_font_scale(1.0)
        constants.FONT_AGENT._font = object()  # sentinel — should NOT be cleared
        constants.set_font_scale(1.0)
        assert constants.FONT_AGENT._font is not None
        constants.FONT_AGENT._font = None  # reset for other tests

    def test_scale_change_fires_listeners(self) -> None:
        """DialogueHistory et al. register callbacks so their cached
        text surfaces rebuild on zoom.  If this regresses, zoom updates
        glyph sizes but the rendered transcript stays at the pre-zoom
        size — exactly the bug the user hit."""
        from hosts.gui import constants

        calls: list[int] = []
        constants.on_font_scale_change(lambda: calls.append(1))

        constants.set_font_scale(1.3)
        assert calls == [1], f"listener not fired on scale change: {calls}"

        constants.set_font_scale(1.3)  # no-op — identical scale
        assert calls == [1], f"listener fired on no-op change: {calls}"

        constants.set_font_scale(1.0)  # reset for downstream tests
        assert calls == [1, 1]

    def test_listener_exception_does_not_break_others(self) -> None:
        from hosts.gui import constants

        good_calls: list[int] = []
        constants.on_font_scale_change(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        constants.on_font_scale_change(lambda: good_calls.append(1))

        # Should not raise — broken listeners must not starve the others.
        constants.set_font_scale(1.4)
        assert good_calls == [1]
        constants.set_font_scale(1.0)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
