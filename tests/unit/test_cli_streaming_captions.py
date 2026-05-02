"""Captions toggle (#19) — host CLI gates dialogue rendering on settings.

When ``captions_enabled=False`` AND TTS is available AND the emission is
tagged ``KIND_DIALOGUE``, the visual comms-window render is suppressed so
the player gets an audio-only mode. Status / code / spec emissions and
the artifact-rendering block are unaffected. With no TTS engine, captions
fall back to ON to avoid silently dropping dialogue.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from a2a.types import Task, TaskState, TaskStatusUpdateEvent

from hosts.cli.streaming import send_and_stream
from kourai_common.messaging import KIND_DIALOGUE, KIND_STATUS, kind_message
from tests.conftest import make_stream_response


def _completed_task() -> MagicMock:
    task = MagicMock(spec=Task)
    task.id = "task-1"
    task.context_id = "ctx-1"
    task.status = MagicMock()
    task.status.state = TaskState.TASK_STATE_COMPLETED
    return task


def _status_event(text: str, kind: str) -> MagicMock:
    """Build a TaskStatusUpdateEvent whose inner message carries the given kind."""
    inner = kind_message(text, kind, context_id="ctx-1", task_id="task-1")
    event = MagicMock(spec=TaskStatusUpdateEvent)
    event.context_id = "ctx-1"
    event.task_id = "task-1"
    event.status = MagicMock()
    event.status.state = TaskState.TASK_STATE_WORKING
    event.status.message = inner
    return event


@pytest.fixture
def _captured(monkeypatch):
    """Capture every visual ``_echo`` call. Stub markdown render and the
    status-formatting helper so the captured string is easy to assert on."""
    captured: list[str] = []
    monkeypatch.setattr("hosts.cli.streaming._echo", captured.append)
    monkeypatch.setattr("hosts.cli.streaming._render_markdown", lambda text: text)
    monkeypatch.setattr("hosts.cli.streaming._extract_artifact_text", lambda _: "")
    monkeypatch.setattr(
        "hosts.cli.streaming._maidenify_status",
        lambda text: (f"[FORMATTED] {text}", "kallos"),
    )
    monkeypatch.setattr(
        "hosts.cli.streaming._extract_status_text",
        lambda event: event.status.message.parts[0].text,
    )
    return captured


def _client_yielding(events) -> MagicMock:
    client = MagicMock()

    async def _events():
        for e in events:
            yield make_stream_response(e)

    client.send_message = MagicMock(return_value=_events())
    return client


@pytest.mark.asyncio
async def test_captions_off_with_tts_suppresses_dialogue_visual(_captured):
    """captions_enabled=False + tts set + KIND_DIALOGUE → no visual."""
    tts = MagicMock()
    tts.speak = AsyncMock()
    dialogue = _status_event('"Welcome back to the forge."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=tts, captions_enabled=False)

    visual = "\n".join(_captured)
    assert "[FORMATTED]" not in visual
    tts.speak.assert_awaited()


@pytest.mark.asyncio
async def test_captions_on_with_tts_renders_dialogue_visual(_captured):
    """captions_enabled=True (default) + tts → visual still renders."""
    tts = MagicMock()
    tts.speak = AsyncMock()
    dialogue = _status_event('"Welcome back to the forge."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=tts, captions_enabled=True)

    visual = "\n".join(_captured)
    assert "[FORMATTED]" in visual
    tts.speak.assert_awaited()


@pytest.mark.asyncio
async def test_captions_off_without_tts_still_renders_dialogue(_captured):
    """captions_enabled=False + tts=None → visual renders so dialogue
    isn't silently dropped (no engine to speak it)."""
    dialogue = _status_event('"Welcome back to the forge."', KIND_DIALOGUE)
    client = _client_yielding([dialogue, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=None, captions_enabled=False)

    visual = "\n".join(_captured)
    assert "[FORMATTED]" in visual


@pytest.mark.asyncio
async def test_captions_off_does_not_affect_status_events(_captured):
    """KIND_STATUS emissions render regardless of the captions toggle —
    captions controls dialogue visibility, not the whole UI."""
    tts = MagicMock()
    tts.speak = AsyncMock()
    status = _status_event("Routing pipeline...", KIND_STATUS)
    client = _client_yielding([status, _completed_task()])

    await send_and_stream(client, "prompt", "ctx-1", tts=tts, captions_enabled=False)

    visual = "\n".join(_captured)
    assert "[FORMATTED]" in visual
    # Status-tagged emissions never speak.
    tts.speak.assert_not_awaited()
