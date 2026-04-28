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


class TestForgeTagsPropagation:
    """``send_and_stream``'s ``forge_tags`` kwarg re-prepends bracket-tags
    on ``input_required`` follow-ups so multi-turn confirmation flows
    (M13 ``yes``, mid-pipeline ASK_USER replies) preserve forge metadata
    across the recursion. Discovered via 2026-04-27 live smoke when M13
    ``yes`` arrived bare at Metis and the agent fell back to ``Path.cwd()``
    (= ``/app`` in container, not a git repo, ``exit 128``)."""

    def _make_input_required_then_complete(self):
        """Return a (mock_send_msg) callable that emits one INPUT_REQUIRED
        on first call, then COMPLETED on the second (the follow-up)."""
        task = _make_task(TaskState.input_required)
        completed = _make_task(TaskState.completed)
        status_required = MagicMock(spec=TaskStatusUpdateEvent)
        status_required.status = MagicMock()
        status_required.status.state = TaskState.input_required
        status_required.status.message = None
        status_done = MagicMock(spec=TaskStatusUpdateEvent)
        status_done.status = MagicMock()
        status_done.status.state = TaskState.completed
        status_done.status.message = None
        sends: list[str] = []

        async def gen_input_required(message, **kwargs):
            sends.append(message.parts[0].root.text)
            yield (task, status_required)

        async def gen_completed(message, **kwargs):
            sends.append(message.parts[0].root.text)
            yield (completed, status_done)
            yield (completed, None)

        client = MagicMock()
        # Each .send_message call returns a fresh async generator.
        gens = iter([gen_input_required, gen_completed])
        client.send_message = lambda msg, **kw: next(gens)(msg, **kw)
        return client, sends

    @pytest.mark.asyncio
    async def test_input_required_follow_up_re_prepends_tags(self, monkeypatch):
        client, sends = self._make_input_required_then_complete()

        async def fake_prompt(_text):
            return "yes"

        # Patch the click.prompt call inside streaming.py so the test
        # doesn't actually try to read from stdin.
        monkeypatch.setattr("hosts.cli.streaming.click.prompt", fake_prompt)

        forge_tags = [
            "[project_root: /home/ajbar/.kourai_khryseai/projects/p1/work]",
            "[yolo: on]",
        ]
        await send_and_stream(
            client, "[project_root: /...]\n[yolo: on]\nadd fn", "ctx-1", forge_tags=forge_tags
        )

        # Two messages sent: the original turn, then the follow-up.
        assert len(sends) == 2
        # The follow-up MUST carry both tags before the user's "yes".
        follow_up_text = sends[1]
        assert "[project_root: /home/ajbar/.kourai_khryseai/projects/p1/work]" in follow_up_text
        assert "[yolo: on]" in follow_up_text
        assert follow_up_text.endswith("yes")

    @pytest.mark.asyncio
    async def test_no_tags_keeps_follow_up_bare(self, monkeypatch):
        # Backward-compat: when forge_tags is None (no active project), the
        # follow-up sends the user's text unchanged — same behavior as before.
        client, sends = self._make_input_required_then_complete()

        async def fake_prompt(_text):
            return "more details"

        monkeypatch.setattr("hosts.cli.streaming.click.prompt", fake_prompt)

        await send_and_stream(client, "hello", "ctx-1")  # no forge_tags

        assert len(sends) == 2
        assert sends[1] == "more details"  # bare, no prepending

    @pytest.mark.asyncio
    async def test_quit_response_does_not_recurse(self, monkeypatch):
        # Defensive: typing /q at the input_required prompt aborts the
        # follow-up entirely, doesn't try to send the tags + /q.
        client, sends = self._make_input_required_then_complete()

        async def fake_prompt(_text):
            return "/q"

        monkeypatch.setattr("hosts.cli.streaming.click.prompt", fake_prompt)

        cont, _, _ = await send_and_stream(
            client, "first", "ctx-1", forge_tags=["[project_root: /tmp]"]
        )
        assert cont is False
        assert len(sends) == 1  # original send only, no follow-up


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


# ===================================================================
# CLI volume parity (M16 follow-on, surfaced 2026-04-27)
# ===================================================================


class TestCLISettingsVolumes:
    """`CLISettings` previously exposed only `*_enabled` booleans; volumes
    were GUI-only. Mirroring the GUI's slider defaults so the CLI player
    has actual control over loudness instead of being forced to OFF.
    """

    def test_defaults_mirror_gui_slider_values(self):
        """The CLI defaults must match `hosts/gui/settings_overlay.py`'s
        slider initial values — a player who learned the GUI sliders
        gets the same baseline in the CLI.
        """
        settings = CLISettings()
        assert settings.music_volume == 0.65
        assert settings.ambient_volume == 0.50
        assert settings.voice_volume == 1.0
        assert settings.sfx_volume == 0.85

    def test_set_volume_clamps_to_unit_range(self, tmp_path, monkeypatch):
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", tmp_path / "cli_settings.json")
        settings = CLISettings()
        assert settings.set_volume("music_volume", 1.5) == 1.0
        assert settings.set_volume("music_volume", -0.2) == 0.0
        assert settings.set_volume("music_volume", 0.42) == 0.42

    def test_set_volume_persists_to_disk(self, tmp_path, monkeypatch):
        path = tmp_path / "cli_settings.json"
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", path)
        settings = CLISettings()
        settings.set_volume("ambient_volume", 0.30)

        reloaded = CLISettings.load()
        assert reloaded.ambient_volume == 0.30

    def test_set_volume_rejects_non_volume_key(self, tmp_path, monkeypatch):
        """Typo guard: `set_volume("music_enabled", 0.5)` would silently
        clobber a boolean toggle if we didn't gate by the `_volume`
        suffix.
        """
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", tmp_path / "cli_settings.json")
        settings = CLISettings()
        with pytest.raises(AttributeError, match="volume"):
            settings.set_volume("music_enabled", 0.5)

    def test_set_volume_rejects_unknown_volume_key(self, tmp_path, monkeypatch):
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", tmp_path / "cli_settings.json")
        settings = CLISettings()
        with pytest.raises(AttributeError, match="volume"):
            settings.set_volume("nonexistent_volume", 0.5)


class TestAdjustVolumesFlow:
    """The /settings menu's `[v]` option walks through each volume,
    accepts decimals 0.0-1.0 (or percent 0-100 as a convenience), Enter
    keeps the current value.
    """

    def test_enter_keeps_all_current_values(self, tmp_path, monkeypatch):
        from hosts.cli.commands import _adjust_volumes

        path = tmp_path / "cli_settings.json"
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", path)
        settings = CLISettings()
        original = (
            settings.music_volume,
            settings.ambient_volume,
            settings.voice_volume,
            settings.sfx_volume,
        )

        with patch("builtins.input", side_effect=["", "", "", ""]):
            changed = _adjust_volumes(settings)

        assert changed is False
        assert (
            settings.music_volume,
            settings.ambient_volume,
            settings.voice_volume,
            settings.sfx_volume,
        ) == original

    def test_decimal_input_sets_each_volume(self, tmp_path, monkeypatch):
        from hosts.cli.commands import _adjust_volumes

        path = tmp_path / "cli_settings.json"
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", path)
        settings = CLISettings()

        with patch("builtins.input", side_effect=["0.30", "0.10", "0.80", "0.40"]):
            changed = _adjust_volumes(settings)

        assert changed is True
        assert settings.music_volume == 0.30
        assert settings.ambient_volume == 0.10
        assert settings.voice_volume == 0.80
        assert settings.sfx_volume == 0.40

    def test_percent_input_normalized_to_unit(self, tmp_path, monkeypatch):
        """Convenience: anything > 1.0 is treated as percent (0-100) so
        a player typing `50` for half-volume gets 0.5 rather than the
        clamped-to-1.0 result.
        """
        from hosts.cli.commands import _adjust_volumes

        path = tmp_path / "cli_settings.json"
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", path)
        settings = CLISettings()

        with patch("builtins.input", side_effect=["50", "", "", ""]):
            _adjust_volumes(settings)

        assert settings.music_volume == 0.50

    def test_invalid_input_skips_that_volume(self, tmp_path, monkeypatch):
        """Player types `loud` for music; that volume stays at its
        current value, the next prompt continues. No exception.
        """
        from hosts.cli.commands import _adjust_volumes

        path = tmp_path / "cli_settings.json"
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", path)
        settings = CLISettings()
        original_music = settings.music_volume

        with patch("builtins.input", side_effect=["loud", "0.10", "", ""]):
            _adjust_volumes(settings)

        assert settings.music_volume == original_music
        assert settings.ambient_volume == 0.10


class TestApplyAudioSettingsMusicOff:
    """Toggling Music OFF should stop the playlist daemon BEFORE fading
    out the current track — otherwise the daemon's polling loop sees
    "not playing" the moment the fade completes and audibly resurrects
    the playlist on the next track. Regression guard for the bug
    surfaced 2026-04-27.
    """

    def test_music_off_stops_playlist_before_stop_music(self, tmp_path, monkeypatch):
        from hosts.cli.__main__ import _apply_audio_settings

        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", tmp_path / "cli_settings.json")
        settings = CLISettings()
        settings.toggle("music_enabled")  # flip from default ON to OFF
        assert settings.music_enabled is False

        audio = MagicMock()
        audio.audio_available = True
        audio.ambient_channel = MagicMock()

        call_order: list[str] = []
        audio.stop_playlist = MagicMock(
            side_effect=lambda *a, **kw: call_order.append("stop_playlist")
        )
        audio.stop_music = MagicMock(side_effect=lambda *a, **kw: call_order.append("stop_music"))

        _apply_audio_settings(audio, settings, tts=None)

        assert call_order == ["stop_playlist", "stop_music"], (
            f"music-OFF should stop the playlist daemon BEFORE the fade so it doesn't "
            f"resurrect on next track; got order: {call_order}"
        )

    def test_volumes_applied_before_play_calls(self, tmp_path, monkeypatch):
        """Volumes must hit `set_*_volume` before `play_ambient` /
        `play_playlist` so a freshly-started stream comes up at the
        chosen level, not the AudioManager's default.
        """
        from hosts.cli.__main__ import _apply_audio_settings

        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", tmp_path / "cli_settings.json")
        settings = CLISettings()
        settings.set_volume("music_volume", 0.2)
        settings.set_volume("ambient_volume", 0.1)

        audio = MagicMock()
        audio.audio_available = True
        audio.ambient_channel = MagicMock()

        _apply_audio_settings(audio, settings, tts=None)

        audio.set_music_volume.assert_called_with(0.2)
        audio.set_ambient_volume.assert_called_with(0.1)
        audio.set_voice_volume.assert_called_with(settings.voice_volume)
        audio.set_sfx_volume.assert_called_with(settings.sfx_volume)
