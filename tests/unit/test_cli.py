"""CLI host: send_and_stream, banner, extract helpers, REPL config."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from a2a.types import Message, Task, TaskArtifactUpdateEvent, TaskState, TaskStatusUpdateEvent

pytest.importorskip("asyncclick")

from hosts.cli.__main__ import (
    _compact_session_memory,
    _format_affinity_bar,
    _format_greeting,
    _maybe_offer_feature_opt_in,
    send_and_stream,
)
from hosts.cli.events import _extract_artifact_text, _extract_status_text
from hosts.cli.settings import CLISettings

# ---------------------------------------------------------------------------
# Extract helpers
# ---------------------------------------------------------------------------


class TestExtractStatusText:
    """_extract_status_text edge cases."""

    def test_returns_empty_for_none_message(self):
        event = MagicMock()
        event.status.message = None
        assert _extract_status_text(event) == ""

    def test_extracts_text_from_parts(self):
        part = MagicMock()
        part.root.text = "Working..."
        event = MagicMock()
        event.status.message.parts = [part]
        assert _extract_status_text(event) == "Working..."

    def test_joins_multiple_parts(self):
        p1 = MagicMock()
        p1.root.text = "line 1"
        p2 = MagicMock()
        p2.root.text = "line 2"
        event = MagicMock()
        event.status.message.parts = [p1, p2]
        assert _extract_status_text(event) == "line 1\nline 2"

    def test_skips_non_text_parts(self):
        p1 = MagicMock()
        del p1.root.text
        p2 = MagicMock()
        p2.root.text = "text part"
        event = MagicMock()
        event.status.message.parts = [p1, p2]
        result = _extract_status_text(event)
        assert "text part" in result


class TestExtractArtifactText:
    """_extract_artifact_text edge cases."""

    def test_returns_empty_for_none_artifact(self):
        event = MagicMock()
        event.artifact = None
        assert _extract_artifact_text(event) == ""

    def test_returns_empty_for_no_parts(self):
        event = MagicMock()
        event.artifact.parts = []
        assert _extract_artifact_text(event) == ""

    def test_extracts_text(self):
        part = MagicMock()
        part.root.text = "final result"
        event = MagicMock()
        event.artifact.parts = [part]
        assert _extract_artifact_text(event) == "final result"


# ---------------------------------------------------------------------------
# send_and_stream — new ClientFactory API
# ---------------------------------------------------------------------------


def _make_task(state: TaskState = TaskState.working) -> MagicMock:
    task = MagicMock(spec=Task)
    task.id = "task-1"
    task.context_id = "ctx-1"
    task.status = MagicMock()
    task.status.state = state
    return task


class TestSendAndStream:
    """Core streaming function using new Client.send_message API."""

    @pytest.mark.asyncio
    async def test_handles_status_updates(self):
        task = _make_task()
        status = MagicMock()
        status.__class__ = TaskStatusUpdateEvent  # type: ignore[assignment]
        status.status.state = TaskState.working
        status.status.message = None

        async def mock_send(message, **kwargs):
            yield (task, status)

        client = MagicMock()
        client.send_message = mock_send

        cont, ctx, tid = await send_and_stream(client, "hello", "ctx-1")
        assert cont is True

    @pytest.mark.asyncio
    async def test_handles_connect_error(self):
        async def mock_send(message, **kwargs):
            raise httpx.ConnectError("refused")
            yield

        client = MagicMock()
        client.send_message = mock_send

        cont, ctx, tid = await send_and_stream(client, "hello", "ctx-1")
        assert cont is True

    @pytest.mark.asyncio
    async def test_handles_timeout(self):
        async def mock_send(message, **kwargs):
            raise httpx.TimeoutException("timed out")
            yield

        client = MagicMock()
        client.send_message = mock_send

        cont, ctx, tid = await send_and_stream(client, "hello", "ctx-1")
        assert cont is True

    @pytest.mark.asyncio
    async def test_handles_message_response(self):
        """Direct Message response (no task created)."""
        part = MagicMock()
        part.root.text = "direct reply"
        msg = MagicMock(spec=Message)
        msg.parts = [part]

        async def mock_send(message, **kwargs):
            yield msg

        client = MagicMock()
        client.send_message = mock_send

        cont, ctx, tid = await send_and_stream(client, "hello", "ctx-1")
        assert cont is True

    @pytest.mark.asyncio
    async def test_verbose_mode(self):
        async def mock_send(message, **kwargs):
            return
            yield

        client = MagicMock()
        client.send_message = mock_send

        cont, ctx, tid = await send_and_stream(client, "hello", "ctx-1", verbose=True)
        assert cont is True

    @pytest.mark.asyncio
    async def test_writes_memoir_entry_on_success(self, monkeypatch, tmp_path):
        from kourai_common.federation.memoir import Memoir
        from kourai_common.federation.memoir_schema import EntrySource

        # Pretend Kallos was the last agent seen during the run.
        monkeypatch.setattr(
            "hosts.cli.streaming.get_last_seen_agent",
            lambda: "kallos",
        )

        client = MagicMock()
        task = _make_task(TaskState.completed)
        artifact_event = MagicMock(spec=TaskArtifactUpdateEvent)
        # Patch artifact extraction to return a deterministic string.
        monkeypatch.setattr(
            "hosts.cli.streaming._extract_artifact_text",
            lambda _: "final lint suggestion",
        )

        async def _events():
            yield (task, artifact_event)
            yield (task, None)

        client.send_message = MagicMock(return_value=_events())

        memoir = Memoir(tmp_path)
        await send_and_stream(
            client,
            "hello",
            "ctx-1",
            memoir=memoir,
            scene_id="session-abc12345.turn-1",
        )

        entries = list(memoir.entries())
        assert len(entries) == 1
        entry = entries[0]
        assert entry.scene_id == "session-abc12345.turn-1"
        assert entry.agent == "kallos"
        assert entry.source is EntrySource.SPECIALIST_PROPOSED
        assert entry.agent_proposed == "final lint suggestion"

    @pytest.mark.asyncio
    async def test_no_memoir_entry_when_memoir_none(self, monkeypatch, tmp_path):
        # Sanity: backward-compatible default — no Memoir kwarg, no write.
        from kourai_common.federation.memoir import Memoir

        monkeypatch.setattr(
            "hosts.cli.streaming.get_last_seen_agent",
            lambda: "kallos",
        )
        monkeypatch.setattr(
            "hosts.cli.streaming._extract_artifact_text",
            lambda _: "final text",
        )

        client = MagicMock()
        task = _make_task(TaskState.completed)
        artifact_event = MagicMock(spec=TaskArtifactUpdateEvent)

        async def _events():
            yield (task, artifact_event)
            yield (task, None)

        client.send_message = MagicMock(return_value=_events())

        await send_and_stream(client, "hello", "ctx-1")
        # No exception, no Memoir written — there isn't one to check.
        # Verify by creating a Memoir at tmp_path and confirming its file
        # does not exist (proxy: nothing wrote to that directory).
        memoir = Memoir(tmp_path)
        assert not memoir.path.exists()


class TestMainCommand:
    """CLI main command configuration."""

    def test_has_agent_option(self):
        from hosts.cli.__main__ import main

        param_names = [p.name for p in main.params]
        assert "agent" in param_names

    def test_has_timeout_option(self):
        from hosts.cli.__main__ import main

        param_names = [p.name for p in main.params]
        assert "timeout_seconds" in param_names


class TestProgressiveOptIn:
    def test_no_prompt_before_min_turn(self):
        settings = CLISettings()
        last_turn, changed, prompted = _maybe_offer_feature_opt_in(
            settings,
            feature="romance",
            turn_counter=2,
            last_nudge_turn=-999,
        )
        assert last_turn == -999
        assert changed is False
        assert prompted is False

    def test_enable_choice_turns_feature_on(self, monkeypatch, tmp_path):
        monkeypatch.setattr("builtins.input", lambda _: "e")
        monkeypatch.setattr(
            "hosts.cli.settings._SETTINGS_FILE",
            tmp_path / "cli_settings.json",
            raising=False,
        )
        settings = CLISettings(romance_enabled=False, romance_nudges_enabled=True)
        last_turn, changed, prompted = _maybe_offer_feature_opt_in(
            settings,
            feature="romance",
            turn_counter=10,
            last_nudge_turn=-999,
        )
        assert last_turn == 10
        assert changed is True
        assert prompted is True
        assert settings.romance_enabled is True

    def test_never_choice_disables_future_nudges(self, monkeypatch, tmp_path):
        monkeypatch.setattr("builtins.input", lambda _: "v")
        monkeypatch.setattr(
            "hosts.cli.settings._SETTINGS_FILE",
            tmp_path / "cli_settings.json",
            raising=False,
        )
        settings = CLISettings(gossip_enabled=False, gossip_nudges_enabled=True)
        last_turn, changed, prompted = _maybe_offer_feature_opt_in(
            settings,
            feature="gossip",
            turn_counter=10,
            last_nudge_turn=-999,
        )
        assert last_turn == 10
        assert changed is True
        assert prompted is True
        assert settings.gossip_nudges_enabled is False


class TestMetricsFormatting:
    def test_affinity_bar_center(self):
        bar = _format_affinity_bar(0.0, width=10)
        assert bar == "█████·····"

    def test_affinity_bar_clamps(self):
        assert _format_affinity_bar(2.0, width=4) == "████"
        assert _format_affinity_bar(-2.0, width=4) == "····"


class TestGreetingFormat:
    """Round 6: greeting must attribute the speaking maiden by name.

    Original line rendered ``( ◡‿◡)✧ Structure IS beauty.`` — face plus
    italic quote with no name. AJ flagged players had to memorize the
    emoji-to-name map. Fix adds the name in front and wraps the line in
    ``"..."`` so M10's italic-on-quoted-line speech convention applies."""

    def test_includes_capitalized_name(self):
        rendered = _format_greeting("metis", "( ◡‿◡)✧", "Structure IS beauty.")
        assert "Metis" in rendered

    def test_includes_face(self):
        rendered = _format_greeting("metis", "( ◡‿◡)✧", "Structure IS beauty.")
        assert "( ◡‿◡)✧" in rendered

    def test_quote_wrapped_in_double_quotes(self):
        # M10 convention: leading-double-quote = dialogue, renders italic.
        rendered = _format_greeting("kallos", "(◕ᴗ◕✿)", "Style isn't optional.")
        assert '"Style isn\'t optional."' in rendered

    def test_lowercased_name_input_is_capitalized(self):
        # Maiden registry keys are lowercase; greeting should display
        # as a proper name, not a key.
        rendered = _format_greeting("hephaestus", "(╭∩╮)⊃━☆ﾟ.*･｡ﾟ", "Ah, you again.")
        assert "Hephaestus" in rendered
        assert "hephaestus" not in rendered.replace("Hephaestus", "")

    def test_name_appears_before_face(self):
        # Reading order matters: name first so the player ties the
        # voice to the face, not the other way around.
        rendered = _format_greeting("techne", "( ⌐■_■)", "Hey gorgeous~")
        # Strip ANSI for stable position checks.
        import re

        plain = re.sub(r"\x1b\[[0-9;]*m", "", rendered)
        assert plain.index("Techne") < plain.index("( ⌐■_■)")
        assert plain.index("( ⌐■_■)") < plain.index('"Hey gorgeous~"')


class TestCompactSessionMemory:
    """``/compact`` slash command — player-triggered transcript compaction
    via Mneme. Universal pattern across the post-leak OSS Claude Code
    clones (ClawCode, Cline, OpenCode); tier-1 lift from the 2026-04-26
    research sweep. The handler must (a) discover agents-with-history
    for the live context_id without hard-coding the roster, (b) force-
    compact each, and (c) emit a Mneme comms-window narrating what
    happened — speech convention per M10 with a leading double-quote so
    the box renders italic dialogue."""

    @pytest.mark.asyncio
    async def test_emits_mneme_comms_when_no_agents(self, monkeypatch):
        # _echo writes to a pre-patched _raw_out stream so capsys can't see it
        # — patch _echo directly per the established pattern in this codebase.
        echoed: list[str] = []
        monkeypatch.setattr(
            "hosts.cli.__main__._echo",
            lambda text="", nl=True: echoed.append(text),
        )
        with (
            patch(
                "hosts.cli.__main__.list_agents_with_history",
                return_value=[],
            ),
            patch("hosts.cli.__main__.compact_memory") as mock_compact,
        ):
            await _compact_session_memory("ctx-empty")

        out = "\n".join(echoed)
        assert "MNEME" in out  # comms-window callsign for Mneme
        assert "fresh" in out.lower()  # the empty-thread message
        mock_compact.assert_not_called()

    @pytest.mark.asyncio
    async def test_iterates_every_agent_and_totals_counts(self, monkeypatch):
        echoed: list[str] = []
        monkeypatch.setattr(
            "hosts.cli.__main__._echo",
            lambda text="", nl=True: echoed.append(text),
        )
        compact_calls: list[tuple[str, str]] = []

        async def _fake_compact(ctx: str, agent: str) -> int:
            compact_calls.append((ctx, agent))
            return {"metis": 3, "techne": 2, "kallos": 0}[agent]

        with (
            patch(
                "hosts.cli.__main__.list_agents_with_history",
                return_value=["kallos", "metis", "techne"],
            ),
            patch(
                "hosts.cli.__main__.compact_memory",
                new=_fake_compact,
            ),
        ):
            await _compact_session_memory("ctx-1")

        out = "\n".join(echoed)
        # All three agents asked, in the order list_agents_with_history returned them.
        assert compact_calls == [
            ("ctx-1", "kallos"),
            ("ctx-1", "metis"),
            ("ctx-1", "techne"),
        ]
        # Total = 5, only metis (3) + techne (2) listed in the roster.
        assert "5" in out
        assert "metis" in out
        assert "techne" in out
        # kallos returned 0 — should NOT appear in the folded roster.
        dialogue_lines = [ln for ln in out.splitlines() if '"' in ln]
        joined = " ".join(dialogue_lines)
        assert "kallos" not in joined.lower()

    @pytest.mark.asyncio
    async def test_zero_total_emits_already_lean_message(self, monkeypatch):
        echoed: list[str] = []
        monkeypatch.setattr(
            "hosts.cli.__main__._echo",
            lambda text="", nl=True: echoed.append(text),
        )

        async def _fake_compact(ctx: str, agent: str) -> int:
            return 0

        with (
            patch(
                "hosts.cli.__main__.list_agents_with_history",
                return_value=["metis"],
            ),
            patch(
                "hosts.cli.__main__.compact_memory",
                new=_fake_compact,
            ),
        ):
            await _compact_session_memory("ctx-1")

        out = "\n".join(echoed)
        assert "lean" in out.lower()
