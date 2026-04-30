"""M11 — GUI attachment send path.

Closes the CLI/GUI multimodal asymmetry. The CLI has shipped image
attachments end-to-end since the Alt+V refactor; the GUI captured
clipboard images into a per-handler ``_pending_images`` list but
``_submit_text`` only forwarded ``(target, text)`` 2-tuples on
``send_q``, so ``GuiClient`` never built a multi-part Message and the
captured image was silently dropped at pipeline completion.

These tests assert:

1. ``send_q`` carries a 3-tuple shape ``(target, text, attachments)``
   from every GUI producer.
2. ``_submit_text`` drains ``_pending_images`` into the put payload and
   resets the list so the next turn doesn't re-send the same image.
3. ``DialogueEntry`` accepts an ``attachments`` kwarg and exposes it
   for renderer consumption; ``DialogueHistory._entry_height`` reserves
   thumbnail space when present.
4. ``GuiClient._send_message`` builds a ``Message`` with a ``TextPart``
   followed by one ``FilePart`` per attachment, mirroring the CLI's
   ``send_and_stream`` shape exactly.
5. ``DemoGuiClient`` accepts the 3-tuple shape (and silently drops
   attachments — demo mode has no real agent on the other end).
"""

from __future__ import annotations

import asyncio
import queue
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("pygame")


# ---------------------------------------------------------------------------
# pygame_event_handler — submit-side wiring
# ---------------------------------------------------------------------------


def _make_handler_with_send_q():
    """Build a minimal PygameEventDispatcher wired to a real Queue.

    Most subsystems are mocked away; we only need the bits that
    ``_submit_text`` and ``_submit_quick_action`` actually touch
    (history, send_q, debug_log, input_bar, portrait, state).
    """
    from hosts.gui.pygame_event_handler import PygameEventDispatcher

    send_q: queue.Queue = queue.Queue()
    handler = PygameEventDispatcher.__new__(PygameEventDispatcher)
    handler.send_q = send_q
    handler.history = MagicMock()
    handler.debug_log = MagicMock()
    handler.input_bar = MagicMock()
    handler.input_bar.waiting_for_agent = None
    handler.input_bar.processing = False
    handler.portrait = MagicMock()

    state = MagicMock()
    state.current_agent = "hephaestus"
    state.reset_for_input = MagicMock()
    handler.state = state

    handler._pending_images = []
    return handler, send_q


class TestSubmitTextTupleShape:
    """``_submit_text`` always pushes the M11 3-tuple to send_q."""

    def test_no_attachments_emits_three_tuple_with_empty_list(self):
        from hosts.gui.maidens import AGENTS

        handler, send_q = _make_handler_with_send_q()
        # AGENTS[hephaestus] needs to exist for the user_quotes lookup.
        assert "hephaestus" in AGENTS

        handler._submit_text("just text, no images")

        item = send_q.get_nowait()
        assert isinstance(item, tuple) and len(item) == 3
        target, text, attachments = item
        assert target == "hephaestus"
        assert text == "just text, no images"
        assert attachments == []

    def test_pending_images_drained_into_send_payload(self):
        handler, send_q = _make_handler_with_send_q()
        handler._pending_images = [
            ("AAAAbase64==", "image/png"),
            ("BBBBbase64==", "image/png"),
        ]

        handler._submit_text("describe this UI bug")

        item = send_q.get_nowait()
        target, text, attachments = item
        assert target == "hephaestus"
        assert text == "describe this UI bug"
        assert attachments == [
            ("AAAAbase64==", "image/png"),
            ("BBBBbase64==", "image/png"),
        ]
        # Drained — next turn must NOT see the same images again.
        assert handler._pending_images == []

    def test_pending_images_drained_even_when_send_fails(self):
        # The drain must come before the put so an exception in put doesn't
        # leave images stuck on the handler. We simulate that by mocking the
        # queue with a put that raises.
        handler, _real_q = _make_handler_with_send_q()
        handler.send_q = MagicMock()
        handler.send_q.put.side_effect = RuntimeError("queue closed")
        handler._pending_images = [("X", "image/png")]

        with pytest.raises(RuntimeError):
            handler._submit_text("text")

        # Drain MUST happen before put, otherwise a transient queue error
        # would re-send the image on the next attempt.
        assert handler._pending_images == []


class TestQuickActionTupleShape:
    """``_submit_quick_action`` also emits a 3-tuple for parity."""

    def test_quick_action_emits_three_tuple_with_empty_attachments(self):
        handler, send_q = _make_handler_with_send_q()

        action = MagicMock()
        action.agent = "kallos"
        action.display_text = "Polish my code"
        action.hidden_prompt = "run ruff format and ruff check --fix"

        handler._submit_quick_action(action)

        item = send_q.get_nowait()
        assert isinstance(item, tuple) and len(item) == 3
        target, text, attachments = item
        assert target == "kallos"
        assert "Polish my code" in text
        assert "run ruff" in text
        assert attachments == []


# ---------------------------------------------------------------------------
# DialogueEntry — attachment field + renderer height accounting
# ---------------------------------------------------------------------------


class TestDialogueEntryAttachments:
    """The dialogue model carries attachments through to the renderer."""

    def test_attachments_default_none(self):
        from hosts.gui.dialogue import DialogueEntry

        e = DialogueEntry("user", "hi", is_user=True)
        assert e.attachments is None
        assert e._attachment_thumbs is None

    def test_attachments_explicit_value_stored(self):
        from hosts.gui.dialogue import DialogueEntry

        atts = [("AAAA==", "image/png")]
        e = DialogueEntry("user", "screenshot:", is_user=True, attachments=atts)
        assert e.attachments is atts

    def test_entry_height_reserves_thumbnail_strip(self):
        from hosts.gui.dialogue import DialogueEntry, DialogueHistory

        history = DialogueHistory()
        plain = DialogueEntry("user", "hi", is_user=True)
        with_atts = DialogueEntry("user", "hi", is_user=True, attachments=[("AAAA==", "image/png")])

        plain_h = history._entry_height(plain, dest_w=600)
        with_atts_h = history._entry_height(with_atts, dest_w=600)

        assert with_atts_h > plain_h
        # Strip is THUMB_H + THUMB_GAP — anything close to that delta is fine.
        assert with_atts_h - plain_h >= history._THUMB_H


# ---------------------------------------------------------------------------
# GuiClient — multi-part Message build mirrors the CLI
# ---------------------------------------------------------------------------


class TestGuiClientMultiPartSend:
    """``GuiClient._send_message`` ships TextPart + FilePart entries."""

    @pytest.mark.asyncio
    async def test_text_only_sends_one_text_part(self):
        from hosts.gui.client import GuiClient

        client = GuiClient(
            send_q=MagicMock(),
            recv_q=MagicMock(),
            agent_url="http://localhost:10000",
        )

        captured: dict = {}

        async def fake_async_client(*_args, **_kwargs):
            class _AsyncCM:
                async def __aenter__(self):
                    return MagicMock()

                async def __aexit__(self, *exc):
                    return False

            return _AsyncCM()

        # Patch the inner machinery — we only care that the Message we'd
        # send carries the right parts. Capture and short-circuit before
        # the network would actually fire.
        with patch("hosts.gui.client.httpx.AsyncClient") as mock_http:
            mock_http.return_value.__aenter__.return_value = MagicMock()
            with (
                patch("hosts.gui.client.A2ACardResolver") as mock_resolver,
                patch("hosts.gui.client.create_client") as mock_create_client,
            ):
                mock_card = MagicMock()
                mock_card.supported_interfaces = [MagicMock(url="http://localhost:10000")]
                mock_resolver.return_value.get_agent_card = _async_return(mock_card)

                mock_a2a_client = MagicMock()

                async def capture_send(request):
                    captured["request"] = request
                    if False:
                        yield None  # make this an async generator

                mock_a2a_client.send_message = capture_send
                mock_create_client.return_value = mock_a2a_client
                mock_create_client.side_effect = _async_return(mock_a2a_client)

                await client._send_message(
                    "http://localhost:10000",
                    "fix this bug",
                    "ctx-1",
                    attachments=None,
                )

        # send_request wraps the Message in a SendMessageRequest — assert
        # against the inner Message's parts.
        message = captured["request"].message
        assert len(message.parts) == 1
        # Single text Part, no file Part — 1.0 wire shape uses HasField discrimination.
        assert message.parts[0].HasField("text")
        assert message.parts[0].text == "fix this bug"

    @pytest.mark.asyncio
    async def test_attachments_become_file_parts(self):
        from hosts.gui.client import GuiClient

        client = GuiClient(
            send_q=MagicMock(),
            recv_q=MagicMock(),
            agent_url="http://localhost:10000",
        )

        captured: dict = {}

        with (
            patch("hosts.gui.client.httpx.AsyncClient") as mock_http,
            patch("hosts.gui.client.A2ACardResolver") as mock_resolver,
            patch("hosts.gui.client.create_client") as mock_create_client,
        ):
            mock_http.return_value.__aenter__.return_value = MagicMock()
            mock_card = MagicMock()
            mock_card.supported_interfaces = [MagicMock(url="http://localhost:10000")]
            mock_resolver.return_value.get_agent_card = _async_return(mock_card)

            mock_a2a_client = MagicMock()

            async def capture_send(request):
                captured["request"] = request
                if False:
                    yield None

            mock_a2a_client.send_message = capture_send
            mock_create_client.side_effect = _async_return(mock_a2a_client)

            await client._send_message(
                "http://localhost:10000",
                "fix the off-by-one in this function",
                "ctx-1",
                attachments=[
                    ("YmFzZTY0cGF5bG9hZDE9PQ==", "image/png"),
                    ("YmFzZTY0cGF5bG9hZDI9PQ==", "image/jpeg"),
                ],
            )

        import base64

        # send_request wraps the Message in a SendMessageRequest — assert
        # against the inner Message's parts.
        message = captured["request"].message
        assert len(message.parts) == 3
        # First Part carries the user prompt; the rest are file Parts.
        assert message.parts[0].HasField("text")
        assert message.parts[1].HasField("raw")
        assert message.parts[2].HasField("raw")
        # 1.0 stores raw bytes directly; round-trip the b64 to verify the helper decoded.
        assert message.parts[1].raw == base64.b64decode("YmFzZTY0cGF5bG9hZDE9PQ==")
        assert message.parts[1].media_type == "image/png"
        assert message.parts[2].raw == base64.b64decode("YmFzZTY0cGF5bG9hZDI9PQ==")
        assert message.parts[2].media_type == "image/jpeg"


# ---------------------------------------------------------------------------
# DemoGuiClient — tolerates 3-tuple, drops attachments
# ---------------------------------------------------------------------------


class TestDemoGuiClientToleratesThreeTuple:
    """Demo mode silently drops attachments (no real agent to consume them)."""

    @pytest.mark.asyncio
    async def test_three_tuple_shape_does_not_crash(self):
        from hosts.gui.demo_client import DemoGuiClient

        send_q: queue.Queue = queue.Queue()
        recv_q: queue.Queue = queue.Queue()
        client = DemoGuiClient(send_q=send_q, recv_q=recv_q, agent_url=None)

        # Push a 3-tuple, then a shutdown sentinel. The run() loop must
        # consume both without raising even though attachments aren't
        # used downstream.
        send_q.put(("hephaestus", "implement csv export", [("AAAA==", "image/png")]))
        send_q.put(None)

        await asyncio.wait_for(client.run(), timeout=2.0)

        # First emitted event is the synthetic "connected" handshake.
        first = recv_q.get_nowait()
        assert first["type"] == "connected"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _async_return(value):
    async def _fn(*_args, **_kwargs):
        return value

    return _fn
