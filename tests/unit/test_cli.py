"""CLI host: send_and_stream, banner, extract helpers, REPL config."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from a2a.types import Message, Task, TaskArtifactUpdateEvent, TaskState, TaskStatusUpdateEvent

from tests.conftest import make_stream_response

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
        part.text = "Working..."
        event = MagicMock()
        event.status.message.parts = [part]
        assert _extract_status_text(event) == "Working..."

    def test_joins_multiple_parts(self):
        p1 = MagicMock()
        p1.text = "line 1"
        p2 = MagicMock()
        p2.text = "line 2"
        event = MagicMock()
        event.status.message.parts = [p1, p2]
        assert _extract_status_text(event) == "line 1\nline 2"

    def test_skips_non_text_parts(self):
        p1 = MagicMock()
        del p1.text
        p2 = MagicMock()
        p2.text = "text part"
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
        part.text = "final result"
        event = MagicMock()
        event.artifact.parts = [part]
        assert _extract_artifact_text(event) == "final result"


# ---------------------------------------------------------------------------
# send_and_stream — new ClientFactory API
# ---------------------------------------------------------------------------


def _make_task(state: TaskState = TaskState.TASK_STATE_WORKING) -> MagicMock:
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
        status = MagicMock(spec=TaskStatusUpdateEvent)
        status.context_id = "ctx-1"
        status.task_id = "task-1"
        status.status = MagicMock()
        status.status.state = TaskState.TASK_STATE_WORKING
        status.status.message = None

        async def mock_send(request, **kwargs):
            yield make_stream_response(status)

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
        part.HasField = lambda name: name == "text"
        part.text = "direct reply"
        msg = MagicMock(spec=Message)
        msg.parts = [part]

        async def mock_send(request, **kwargs):
            yield make_stream_response(msg)

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
        task = _make_task(TaskState.TASK_STATE_COMPLETED)
        artifact_event = MagicMock(spec=TaskArtifactUpdateEvent)
        artifact_event.context_id = "ctx-1"
        artifact_event.task_id = "task-1"
        # Patch artifact extraction to return a deterministic string.
        monkeypatch.setattr(
            "hosts.cli.streaming._extract_artifact_text",
            lambda _: "final lint suggestion",
        )

        async def _events():
            yield make_stream_response(artifact_event)
            yield make_stream_response(task)

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
        task = _make_task(TaskState.TASK_STATE_COMPLETED)
        artifact_event = MagicMock(spec=TaskArtifactUpdateEvent)
        artifact_event.context_id = "ctx-1"
        artifact_event.task_id = "task-1"

        async def _events():
            yield make_stream_response(artifact_event)
            yield make_stream_response(task)

        client.send_message = MagicMock(return_value=_events())

        await send_and_stream(client, "hello", "ctx-1")
        # No exception, no Memoir written — there isn't one to check.
        # Verify by creating a Memoir at tmp_path and confirming its file
        # does not exist (proxy: nothing wrote to that directory).
        memoir = Memoir(tmp_path)
        assert not memoir.path.exists()


class TestConnectWithUrlOverride:
    """``_connect_with_url_override`` must return ``(client, card)`` so the
    CLI can read ``card.name`` / ``card.skills`` on startup without a
    second resolver round-trip. v1.0 SDK retired ``client.get_card()``; the
    helper centralizes the v0.3 → 1.0 boundary at one site. This test
    locks the contract so a future SDK migration doesn't quietly drop the
    card from the return tuple."""

    @pytest.mark.asyncio
    async def test_returns_client_and_card_tuple(self, monkeypatch):
        from a2a.client import ClientConfig
        from a2a.types import AgentCard

        from hosts.cli.streaming import _connect_with_url_override

        # Real card, mock everything else — the helper patches the URL on
        # the card's interfaces, so the assertion targets that mutation.
        live_card = MagicMock(spec=AgentCard)
        live_card.name = "Test Agent"
        interface = MagicMock()
        interface.url = "http://internal-host:10000/"
        live_card.supported_interfaces = [interface]

        mock_resolver = MagicMock()
        mock_resolver.get_agent_card = AsyncMock(return_value=live_card)

        mock_client = MagicMock()

        async def fake_create_client(card, client_config):
            return mock_client

        monkeypatch.setattr("hosts.cli.streaming.A2ACardResolver", lambda *_a, **_kw: mock_resolver)
        monkeypatch.setattr("hosts.cli.streaming.create_client", fake_create_client)

        config = ClientConfig(streaming=True, httpx_client=MagicMock())

        result = await _connect_with_url_override("http://localhost:10000/", config)

        # Locked contract: returns a 2-tuple, NOT a bare Client. Future SDK
        # migrations that route around this helper will break this test
        # rather than silently regressing CLI startup.
        assert isinstance(result, tuple)
        assert len(result) == 2
        client, card = result
        assert client is mock_client
        assert card is live_card
        # The helper's other contract: every supported_interface URL is
        # rewritten to the reachable host URL so the SDK's outbound calls
        # don't hit the unreachable internal hostname.
        assert all(iface.url == "http://localhost:10000/" for iface in card.supported_interfaces)


class TestForgeMetadataPropagation:
    """``send_and_stream``'s ``forge_metadata`` kwarg propagates the forge
    context across ``input_required`` follow-ups so multi-turn confirmation
    flows (M13 ``yes``, mid-pipeline ASK_USER replies) preserve forge state
    across the recursion. Discovered via 2026-04-27 live smoke when M13
    ``yes`` arrived bare at Metis and the agent fell back to ``Path.cwd()``
    (= ``/app`` in container, not a git repo, ``exit 128``). Migrated to
    ``Message.metadata`` in M7 Phase 5."""

    def _make_input_required_then_complete(self):
        """Return a (mock_send_msg) callable that emits one INPUT_REQUIRED
        on first call, then COMPLETED on the second (the follow-up)."""
        completed = _make_task(TaskState.TASK_STATE_COMPLETED)
        status_required = MagicMock(spec=TaskStatusUpdateEvent)
        status_required.context_id = "ctx-1"
        status_required.task_id = "task-1"
        status_required.status = MagicMock()
        status_required.status.state = TaskState.TASK_STATE_INPUT_REQUIRED
        status_required.status.message = None
        status_done = MagicMock(spec=TaskStatusUpdateEvent)
        status_done.context_id = "ctx-1"
        status_done.task_id = "task-1"
        status_done.status = MagicMock()
        status_done.status.state = TaskState.TASK_STATE_COMPLETED
        status_done.status.message = None
        sends: list[str] = []

        async def gen_input_required(request, **kwargs):
            sends.append(request.message.parts[0].text)
            yield make_stream_response(status_required)

        async def gen_completed(request, **kwargs):
            sends.append(request.message.parts[0].text)
            yield make_stream_response(status_done)
            yield make_stream_response(completed)

        client = MagicMock()
        # Each .send_message call returns a fresh async generator.
        gens = iter([gen_input_required, gen_completed])
        client.send_message = lambda req, **kw: next(gens)(req, **kw)
        return client, sends

    @pytest.mark.asyncio
    async def test_input_required_follow_up_carries_forge_metadata(self, monkeypatch):
        client, sends = self._make_input_required_then_complete()
        captured_metadata: list[dict] = []

        async def gen_input_required(request, **kwargs):
            sends.append(request.message.parts[0].text)
            captured_metadata.append(dict(request.message.metadata))
            status_required = MagicMock(spec=TaskStatusUpdateEvent)
            status_required.context_id = "ctx-1"
            status_required.task_id = "task-1"
            status_required.status = MagicMock()
            status_required.status.state = TaskState.TASK_STATE_INPUT_REQUIRED
            status_required.status.message = None
            yield make_stream_response(status_required)

        async def gen_completed(request, **kwargs):
            sends.append(request.message.parts[0].text)
            captured_metadata.append(dict(request.message.metadata))
            completed = _make_task(TaskState.TASK_STATE_COMPLETED)
            status_done = MagicMock(spec=TaskStatusUpdateEvent)
            status_done.context_id = "ctx-1"
            status_done.task_id = "task-1"
            status_done.status = MagicMock()
            status_done.status.state = TaskState.TASK_STATE_COMPLETED
            status_done.status.message = None
            yield make_stream_response(status_done)
            yield make_stream_response(completed)

        gens = iter([gen_input_required, gen_completed])
        client.send_message = lambda req, **kw: next(gens)(req, **kw)

        async def fake_prompt(_text):
            return "yes"

        monkeypatch.setattr("hosts.cli.streaming.click.prompt", fake_prompt)

        forge_metadata = {
            "project_root": "/home/ajbar/.kourai_khryseai/projects/p1/work",
            "yolo": "on",
        }
        await send_and_stream(client, "add fn", "ctx-1", forge_metadata=forge_metadata)

        # Two messages sent: the original turn, then the follow-up.
        assert len(sends) == 2
        # The follow-up must carry the same metadata so specialists still
        # see project_root + yolo on the resumed task.
        follow_up_text = sends[1]
        assert follow_up_text == "yes"
        follow_up_meta = captured_metadata[1]
        assert follow_up_meta.get("project_root") == forge_metadata["project_root"]
        assert follow_up_meta.get("yolo") == "on"

    @pytest.mark.asyncio
    async def test_quit_response_does_not_recurse(self, monkeypatch):
        # Defensive: typing /q at the input_required prompt aborts the
        # follow-up entirely.
        client, sends = self._make_input_required_then_complete()

        async def fake_prompt(_text):
            return "/q"

        monkeypatch.setattr("hosts.cli.streaming.click.prompt", fake_prompt)

        cont, _, _ = await send_and_stream(
            client,
            "first",
            "ctx-1",
            forge_metadata={"project_root": "/tmp"},  # noqa: S108
        )
        assert cont is False
        assert len(sends) == 1  # original send only, no follow-up

    @pytest.mark.asyncio
    async def test_m13_fix_carries_original_request_in_metadata(self, monkeypatch):
        """M13 regression — the resumed turn's metadata must include the
        original development request as ``original_request`` so Hephaestus
        relays the actual ask (not the confirmation token like ``yes``)
        to specialists.
        """
        sends: list[str] = []
        captured_metadata: list[dict] = []

        async def gen_input_required(request, **kwargs):
            sends.append(request.message.parts[0].text)
            captured_metadata.append(dict(request.message.metadata))
            status_required = MagicMock(spec=TaskStatusUpdateEvent)
            status_required.context_id = "ctx-1"
            status_required.task_id = "task-1"
            status_required.status = MagicMock()
            status_required.status.state = TaskState.TASK_STATE_INPUT_REQUIRED
            status_required.status.message = None
            yield make_stream_response(status_required)

        async def gen_completed(request, **kwargs):
            sends.append(request.message.parts[0].text)
            captured_metadata.append(dict(request.message.metadata))
            completed = _make_task(TaskState.TASK_STATE_COMPLETED)
            status_done = MagicMock(spec=TaskStatusUpdateEvent)
            status_done.context_id = "ctx-1"
            status_done.task_id = "task-1"
            status_done.status = MagicMock()
            status_done.status.state = TaskState.TASK_STATE_COMPLETED
            status_done.status.message = None
            yield make_stream_response(status_done)
            yield make_stream_response(completed)

        client = MagicMock()
        gens = iter([gen_input_required, gen_completed])
        client.send_message = lambda req, **kw: next(gens)(req, **kw)

        async def fake_prompt(_text):
            return "yes"

        monkeypatch.setattr("hosts.cli.streaming.click.prompt", fake_prompt)

        await send_and_stream(client, "implement fizzbuzz", "ctx-1")

        assert len(sends) == 2
        assert sends[1] == "yes"
        # Resumed turn's metadata must echo the player's original
        # development ask so the orchestrator doesn't treat the
        # confirmation token as the spec body.
        follow_up_meta = captured_metadata[1]
        assert follow_up_meta.get("original_request") == "implement fizzbuzz"


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
    """Greeting must attribute the speaking maiden by name.

    Without the name prefix the line renders as
    ``( ◡‿◡)✧ Structure IS beauty.`` — face plus italic quote with no
    name — forcing players to memorize the emoji-to-name map. Prepending
    the name and wrapping the quote in ``"..."`` makes the
    italic-on-quoted-line speech convention read naturally."""

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


class TestSettingsSyncModeChoice:
    """M20 sub-task 4 — `/settings s` cycles dialogue_sync_mode between
    audio-led and instant. Persists to disk, applied to next dialogue line.
    """

    def test_s_choice_cycles_audio_led_to_instant(self, tmp_path, monkeypatch):
        from hosts.cli.commands import _apply_settings_choice

        path = tmp_path / "cli_settings.json"
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", path)
        # Seed disk state to audio-led (the default).
        CLISettings().save()

        changed = _apply_settings_choice("s")
        assert changed is True

        reloaded = CLISettings.load()
        assert reloaded.dialogue_sync_mode == "instant"

    def test_s_choice_cycles_instant_back_to_audio_led(self, tmp_path, monkeypatch):
        from hosts.cli.commands import _apply_settings_choice

        path = tmp_path / "cli_settings.json"
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", path)
        s = CLISettings()
        s.dialogue_sync_mode = "instant"
        s.save()

        changed = _apply_settings_choice("s")
        assert changed is True

        reloaded = CLISettings.load()
        assert reloaded.dialogue_sync_mode == "audio-led"

    def test_uppercase_s_also_works(self, tmp_path, monkeypatch):
        """Match the case-insensitivity of the existing r/v shortcuts."""
        from hosts.cli.commands import _apply_settings_choice

        path = tmp_path / "cli_settings.json"
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", path)
        CLISettings().save()

        changed = _apply_settings_choice("S")
        assert changed is True
        assert CLISettings.load().dialogue_sync_mode == "instant"


class TestSettingsSessionModeChoice:
    """Puck-tutorial spec — `[0] Session Mode` in `/settings` flips
    between gamified and focused via `apply_mode_cascade`. Diegetic line
    prints on flip; bidirectional. Spec:
    `docs/architecture/puck-first-run-tutorial.md` Section 3.
    """

    def _isolate_stores(self, tmp_path, monkeypatch):
        """Same pattern as test_mode_cascade._isolated_stores fixture
        but inline since this test class lives in test_cli.py."""
        import kourai_common.player as player_mod

        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        monkeypatch.setattr(player_mod, "PLAYER_DIR", tmp_path)
        monkeypatch.setattr(player_mod, "PROFILES_DIR", profiles_dir)
        monkeypatch.setattr(player_mod, "ACTIVE_PROFILE_FILE", tmp_path / "active_profile.txt")
        monkeypatch.setattr(player_mod, "_LEGACY_PLAYER_FILE", tmp_path / "player.json")
        if hasattr(player_mod, "_profile_cache"):
            player_mod._profile_cache = None
        if hasattr(player_mod, "_profile_cache_ts"):
            player_mod._profile_cache_ts = 0.0
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", tmp_path / "cli_settings.json")

    def test_panel_renders_zero_entry_with_gamified_when_current_is_gamified(
        self, tmp_path, monkeypatch
    ):
        from hosts.cli.commands import _print_settings_panel
        from kourai_common.player_profile import PlayerProfile

        self._isolate_stores(tmp_path, monkeypatch)
        profile = PlayerProfile()
        profile.preferences["experience_mode"] = "gamified"
        profile.save()

        echoed: list[str] = []
        monkeypatch.setattr(
            "hosts.cli.commands._echo",
            lambda text="": echoed.append(text),
        )
        _print_settings_panel(CLISettings.load())

        assert any("[0] Session Mode" in line and "gamified" in line for line in echoed)

    def test_panel_renders_zero_entry_with_focused_when_current_is_focused(
        self, tmp_path, monkeypatch
    ):
        from hosts.cli.commands import _print_settings_panel
        from kourai_common.player_profile import PlayerProfile

        self._isolate_stores(tmp_path, monkeypatch)
        profile = PlayerProfile()
        profile.preferences["experience_mode"] = "focused"
        profile.save()

        echoed: list[str] = []
        monkeypatch.setattr(
            "hosts.cli.commands._echo",
            lambda text="": echoed.append(text),
        )
        _print_settings_panel(CLISettings.load())

        assert any("[0] Session Mode" in line and "focused" in line for line in echoed)

    def test_zero_choice_flips_gamified_to_focused_with_diegetic_line(self, tmp_path, monkeypatch):
        from hosts.cli.commands import _apply_settings_choice
        from kourai_common.player_profile import PlayerProfile

        self._isolate_stores(tmp_path, monkeypatch)
        profile = PlayerProfile()
        profile.preferences["experience_mode"] = "gamified"
        profile.save()

        echoed: list[str] = []
        monkeypatch.setattr(
            "hosts.cli.commands._echo",
            lambda text="": echoed.append(text),
        )
        changed = _apply_settings_choice("0")
        assert changed is True

        # Persisted to disk.
        reloaded = PlayerProfile.load()
        assert reloaded is not None
        assert reloaded.preferences["experience_mode"] == "focused"
        # Cascade actually flipped — gossip should be False under focused.
        assert CLISettings.load().gossip_enabled is False
        # Diegetic line per spec — "The forge falls quiet." on the
        # gamified→focused transition.
        out = "\n".join(echoed)
        assert "The forge falls quiet" in out

    def test_zero_choice_flips_focused_to_gamified_with_diegetic_line(self, tmp_path, monkeypatch):
        from hosts.cli.commands import _apply_settings_choice
        from kourai_common.player_profile import PlayerProfile

        self._isolate_stores(tmp_path, monkeypatch)
        profile = PlayerProfile()
        profile.preferences["experience_mode"] = "focused"
        profile.save()

        echoed: list[str] = []
        monkeypatch.setattr(
            "hosts.cli.commands._echo",
            lambda text="": echoed.append(text),
        )
        changed = _apply_settings_choice("0")
        assert changed is True

        reloaded = PlayerProfile.load()
        assert reloaded is not None
        assert reloaded.preferences["experience_mode"] == "gamified"
        assert CLISettings.load().gossip_enabled is True
        out = "\n".join(echoed)
        # Diegetic line per spec — focused→gamified transition.
        assert "Puck slips back through the door" in out
