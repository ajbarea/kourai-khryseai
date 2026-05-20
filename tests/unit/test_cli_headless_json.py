"""--json headless output emits one JSON record per agent event.

Mirrors the OpenAI Codex --json / Claude Code stream-json convention:
each line is a self-contained JSON object with a ``type`` discriminator
("message" | "status" | "result") so agent pipelines can ``jq`` the
stream without parsing partial JSON or ANSI noise.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from a2a.types import Message, TaskArtifactUpdateEvent, TaskStatusUpdateEvent

from hosts.cli import headless as headless_mod
from tests.conftest import make_stream_response


def _message_event(text: str, sender: str = "hephaestus") -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.sender_id = sender
    part = MagicMock()
    part.HasField = lambda name: name == "text"
    part.text = text
    msg.parts = [part]
    return msg


def _status_event() -> MagicMock:
    return MagicMock(spec=TaskStatusUpdateEvent)


def _artifact_event() -> MagicMock:
    return MagicMock(spec=TaskArtifactUpdateEvent)


def _yielding_client(events):
    client = MagicMock()

    async def _gen():
        for e in events:
            yield make_stream_response(e)

    client.send_message = MagicMock(return_value=_gen())
    client.close = AsyncMock()
    return client


@pytest.fixture
def _patch_headless(monkeypatch):
    """Patch the A2A boundary so the streaming path is fully under test control."""
    monkeypatch.setattr(headless_mod, "make_a2a_http_client", lambda **_: MagicMock())
    monkeypatch.setattr(headless_mod, "user_message", lambda *a, **k: MagicMock())
    monkeypatch.setattr(headless_mod, "send_request", lambda m: MagicMock())
    monkeypatch.setattr(headless_mod, "_extract_status_text", lambda _e: "working on forge order")
    monkeypatch.setattr(headless_mod, "_extract_artifact_text", lambda _e: "final answer")


@pytest.fixture
def _capture_echo(monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr(headless_mod.click, "echo", lambda s=None, err=False: captured.append(s))
    return captured


@pytest.mark.asyncio
async def test_json_mode_emits_jsonl_per_event_type(_patch_headless, _capture_echo, monkeypatch):
    """One line per Message/Status/Artifact, each parseable as JSON with type discriminator."""
    client = _yielding_client([_message_event("hello, smith"), _status_event(), _artifact_event()])

    async def _fake_connect(_url, _cfg):
        return client, MagicMock()

    monkeypatch.setattr(headless_mod, "_connect_with_url_override", _fake_connect)

    await headless_mod._headless("http://x", "prompt", 30, verbose=False, json_mode=True)

    records = [json.loads(line) for line in _capture_echo if line]
    types = [r["type"] for r in records]
    assert types == ["message", "status", "result"]

    msg = records[0]
    assert msg["agent"] == "hephaestus"
    assert msg["text"] == "hello, smith"
    assert "ts" in msg

    assert records[1]["text"] == "working on forge order"
    assert records[2]["text"] == "final answer"


@pytest.mark.asyncio
async def test_non_json_mode_only_emits_final_artifact(_patch_headless, _capture_echo, monkeypatch):
    """Default mode: stdout gets only the final artifact text (for piping)."""
    client = _yielding_client([_message_event("chatter"), _status_event(), _artifact_event()])

    async def _fake_connect(_url, _cfg):
        return client, MagicMock()

    monkeypatch.setattr(headless_mod, "_connect_with_url_override", _fake_connect)

    await headless_mod._headless("http://x", "prompt", 30, verbose=False, json_mode=False)

    stdout_lines = [s for s in _capture_echo if s]
    assert stdout_lines == ["final answer"]
