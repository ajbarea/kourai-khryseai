"""M13 — wiring CONFIRM_ORDER through the executor → A2A INPUT_REQUIRED.

These tests cover the hand-off between Hephaestus's routing call (which
returns the raw ``CONFIRM_ORDER:`` string from the LLM) and the executor
(which has to recognise the token, render the read-back to the player as
an ``INPUT_REQUIRED`` event, and let the A2A task pause until the player
responds in the same context_id).

The resume side is implicit by design — the next user message lands in
the same context_id, the LLM sees the prior CONFIRM_ORDER turn in
memory, and emits the agent list (response option #1) on the next
routing call. No explicit "resume metadata" plumbing is needed.

Plus the ``/yolo`` opt-out: CLI prepends a ``[yolo: on]`` text tag the
router strips and reacts to by augmenting its system prompt to bypass
the gate. Same pattern as ``[project_root: …]`` and
``[relationship_tiers: …]``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDeterminePipelineForwardsConfirmOrder:
    """``determine_pipeline`` must forward the LLM's CONFIRM_ORDER response
    string verbatim, the same way it forwards ASK_USER / CHAT today."""

    @pytest.mark.asyncio
    async def test_clear_tier_forwarded(self):
        from agents.hephaestus.agent import determine_pipeline

        with patch(
            "agents.hephaestus.agent.chat",
            new_callable=AsyncMock,
            return_value=(
                'CONFIRM_ORDER: clear "double(n) in src/math.py with a test. Light the forge?"'
            ),
        ):
            result = await determine_pipeline("add a double function")

        assert isinstance(result, str)
        assert result.startswith("CONFIRM_ORDER:")
        assert "clear" in result
        assert "Light the forge?" in result

    @pytest.mark.asyncio
    async def test_smart_tier_forwarded(self):
        from agents.hephaestus.agent import determine_pipeline

        with patch(
            "agents.hephaestus.agent.chat",
            new_callable=AsyncMock,
            return_value='CONFIRM_ORDER: smart "tradeoffs?"',
        ):
            result = await determine_pipeline("add divide function")

        assert result.startswith("CONFIRM_ORDER:")
        assert "smart" in result

    @pytest.mark.asyncio
    async def test_clarify_tier_forwarded(self):
        from agents.hephaestus.agent import determine_pipeline

        with patch(
            "agents.hephaestus.agent.chat",
            new_callable=AsyncMock,
            return_value='CONFIRM_ORDER: clarify "Which functions?"',
        ):
            result = await determine_pipeline("speed it up")

        assert result.startswith("CONFIRM_ORDER:")
        assert "clarify" in result

    @pytest.mark.asyncio
    async def test_chat_response_still_forwarded(self):
        # Existing ASK_USER / CHAT branches unchanged — regression guard.
        from agents.hephaestus.agent import determine_pipeline

        with patch(
            "agents.hephaestus.agent.chat",
            new_callable=AsyncMock,
            return_value='CHAT: "The forge is hot."',
        ):
            result = await determine_pipeline("hi")

        assert isinstance(result, str)
        assert result.startswith("CHAT:")

    @pytest.mark.asyncio
    async def test_pipeline_list_response_still_returned(self):
        # Resume turn — player has confirmed; LLM emits agent list.
        from agents.hephaestus.agent import determine_pipeline

        with patch(
            "agents.hephaestus.agent.chat",
            new_callable=AsyncMock,
            return_value="metis, techne, dokimasia, kallos, mneme",
        ):
            result = await determine_pipeline("[PLAYER CONFIRMED]: yes")

        assert isinstance(result, list)
        assert "metis" in result


class TestYoloBypass:
    """``[yolo: on]`` text-tag bypasses the gate via system-prompt augmentation."""

    def test_extract_yolo_strips_tag_and_returns_true(self):
        from agents.hephaestus.agent import extract_yolo

        clean, yolo = extract_yolo("[yolo: on]\nadd a function")
        assert yolo is True
        assert clean == "add a function"

    def test_extract_yolo_case_insensitive(self):
        from agents.hephaestus.agent import extract_yolo

        clean, yolo = extract_yolo("[YOLO: ON]\nadd a function")
        assert yolo is True
        assert clean == "add a function"

    def test_extract_yolo_absent_returns_false(self):
        from agents.hephaestus.agent import extract_yolo

        clean, yolo = extract_yolo("add a function")
        assert yolo is False
        assert clean == "add a function"

    def test_extract_yolo_does_not_match_quoted_yolo_in_text(self):
        from agents.hephaestus.agent import extract_yolo

        # The bracketed-tag format is what we strip — bare "yolo" in
        # the prompt body must NOT trigger the bypass.
        clean, yolo = extract_yolo("teach me about yolo programming")
        assert yolo is False
        assert "yolo" in clean

    @pytest.mark.asyncio
    async def test_yolo_augments_system_prompt(self):
        # Verifies the bypass path actually reaches the LLM. We capture
        # the messages handed to ``chat`` and assert the system prompt
        # contains the YOLO MODE instruction.
        from agents.hephaestus.agent import determine_pipeline

        captured: dict = {}

        async def capture_chat(agent, messages, **kwargs):
            captured["messages"] = messages
            return "metis, techne, dokimasia, kallos, mneme"

        with patch("agents.hephaestus.agent.chat", side_effect=capture_chat):
            await determine_pipeline("[yolo: on]\nadd a function")

        system_msg = next(m for m in captured["messages"] if m["role"] == "system")
        assert "YOLO MODE" in system_msg["content"]
        assert "Skip CONFIRM_ORDER" in system_msg["content"]

    @pytest.mark.asyncio
    async def test_no_yolo_keeps_system_prompt_clean(self):
        # Default path — no YOLO MODE injection.
        from agents.hephaestus.agent import determine_pipeline

        captured: dict = {}

        async def capture_chat(agent, messages, **kwargs):
            captured["messages"] = messages
            return 'CONFIRM_ORDER: clear "x?"'

        with patch("agents.hephaestus.agent.chat", side_effect=capture_chat):
            await determine_pipeline("add a function")

        system_msg = next(m for m in captured["messages"] if m["role"] == "system")
        assert "YOLO MODE" not in system_msg["content"]


class TestAutoApproveReadsBypass:
    """``[auto_approve_reads: on]`` — granular middle ground from
    ``/permissions auto_approve_reads``. Skips CONFIRM_ORDER for read-
    only / planning-only pipelines; still gates anything that touches
    disk. Tier-2 lift from the 2026-04-26 OSS-CC research sweep."""

    def test_extract_auto_approve_reads_strips_tag_and_returns_true(self):
        from agents.hephaestus.agent import extract_auto_approve_reads

        clean, on = extract_auto_approve_reads("[auto_approve_reads: on]\nplan a feature")
        assert on is True
        assert clean == "plan a feature"

    def test_extract_auto_approve_reads_case_insensitive(self):
        from agents.hephaestus.agent import extract_auto_approve_reads

        clean, on = extract_auto_approve_reads("[AUTO_APPROVE_READS: ON]\nplan a feature")
        assert on is True
        assert clean == "plan a feature"

    def test_extract_auto_approve_reads_absent_returns_false(self):
        from agents.hephaestus.agent import extract_auto_approve_reads

        clean, on = extract_auto_approve_reads("plan a feature")
        assert on is False
        assert clean == "plan a feature"

    def test_extract_does_not_match_substring_in_text(self):
        from agents.hephaestus.agent import extract_auto_approve_reads

        # The bracket-tag format is what we strip — bare phrase in body must NOT trigger.
        clean, on = extract_auto_approve_reads("explain what auto_approve_reads does")
        assert on is False
        assert "auto_approve_reads" in clean

    @pytest.mark.asyncio
    async def test_augments_system_prompt(self):
        from agents.hephaestus.agent import determine_pipeline

        captured: dict = {}

        async def capture_chat(agent, messages, **kwargs):
            captured["messages"] = messages
            return "metis"

        with patch("agents.hephaestus.agent.chat", side_effect=capture_chat):
            await determine_pipeline("[auto_approve_reads: on]\nplan a feature")

        system_msg = next(m for m in captured["messages"] if m["role"] == "system")
        assert "AUTO_APPROVE_READS" in system_msg["content"]
        # Must explicitly call out the three mutating agents so the LLM
        # doesn't widen the bypass to write paths.
        assert "techne" in system_msg["content"].lower()
        assert "kallos" in system_msg["content"].lower()
        assert "dokimasia" in system_msg["content"].lower()

    @pytest.mark.asyncio
    async def test_yolo_wins_when_both_set(self):
        # Defensive: if both flags are on, /yolo's broader bypass takes
        # precedence — auto_approve_reads is the narrower middle ground.
        from agents.hephaestus.agent import determine_pipeline

        captured: dict = {}

        async def capture_chat(agent, messages, **kwargs):
            captured["messages"] = messages
            return "metis, techne"

        with patch("agents.hephaestus.agent.chat", side_effect=capture_chat):
            await determine_pipeline("[yolo: on]\n[auto_approve_reads: on]\nbuild a feature")

        system_msg = next(m for m in captured["messages"] if m["role"] == "system")
        assert "YOLO MODE" in system_msg["content"]
        # The auto_approve_reads block should NOT also be appended —
        # the elif in determine_pipeline guards against double-injection.
        assert "AUTO_APPROVE_READS" not in system_msg["content"]


class TestCLISettingsYoloField:
    """``CLISettings`` carries the persisted yolo flag with safe defaults."""

    def test_yolo_default_off(self):
        from hosts.cli.settings import CLISettings

        settings = CLISettings()
        assert settings.yolo_enabled is False

    def test_toggle_flips_yolo(self, tmp_path, monkeypatch):
        # Redirect the settings file to a tmp path so we don't trash
        # the real user's saved settings during the test.
        settings_file = tmp_path / "cli_settings.json"
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", settings_file)

        from hosts.cli.settings import CLISettings

        settings = CLISettings()
        new_value = settings.toggle("yolo_enabled")
        assert new_value is True
        assert settings.yolo_enabled is True

        # Persists across load.
        reloaded = CLISettings.load()
        assert reloaded.yolo_enabled is True

    def test_load_tolerates_unknown_keys(self, tmp_path, monkeypatch):
        # Forward-compat: an old settings.json from a future-rolled-back
        # build that has unknown keys should NOT crash CLISettings.load.
        # This regression existed before the M13 change — fixed in passing.
        settings_file = tmp_path / "cli_settings.json"
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", settings_file)

        import json

        from hosts.cli.settings import CLISettings

        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text(
            json.dumps(
                {
                    "voice_enabled": False,
                    "yolo_enabled": True,
                    "future_field_we_dont_know_about": "lol",
                }
            ),
            encoding="utf-8",
        )

        loaded = CLISettings.load()
        assert loaded.voice_enabled is False
        assert loaded.yolo_enabled is True
        # Unknown key dropped silently — no crash.
        assert not hasattr(loaded, "future_field_we_dont_know_about")


class TestCLISettingsAutoApproveReadsField:
    """``CLISettings`` carries the persisted auto_approve_reads flag."""

    def test_default_off(self):
        from hosts.cli.settings import CLISettings

        assert CLISettings().auto_approve_reads is False

    def test_toggle_persists(self, tmp_path, monkeypatch):
        settings_file = tmp_path / "cli_settings.json"
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", settings_file)

        from hosts.cli.settings import CLISettings

        settings = CLISettings()
        new_value = settings.toggle("auto_approve_reads")
        assert new_value is True
        assert CLISettings.load().auto_approve_reads is True


class TestPermissionsCommand:
    """``/permissions`` slash handler — view + toggle pipeline gates."""

    def test_bare_lists_all_gates_with_state(self, tmp_path, monkeypatch):
        # Sandbox the settings file; we don't want the test mutating the user's.
        settings_file = tmp_path / "cli_settings.json"
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", settings_file)

        echoed: list[str] = []
        monkeypatch.setattr(
            "hosts.cli.__main__._echo",
            lambda text="", nl=True: echoed.append(text),
        )

        from hosts.cli.__main__ import _handle_permissions_command
        from hosts.cli.settings import CLISettings

        _handle_permissions_command("/permissions", CLISettings())
        out = "\n".join(echoed)

        # Both gates must appear in the listing with their default state.
        assert "yolo" in out
        assert "reads" in out
        assert "OFF" in out
        assert "Permissions" in out

    def test_toggles_named_gate_and_persists(self, tmp_path, monkeypatch):
        settings_file = tmp_path / "cli_settings.json"
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", settings_file)

        echoed: list[str] = []
        monkeypatch.setattr(
            "hosts.cli.__main__._echo",
            lambda text="", nl=True: echoed.append(text),
        )

        from hosts.cli.__main__ import _handle_permissions_command
        from hosts.cli.settings import CLISettings

        settings = CLISettings()
        _handle_permissions_command("/permissions reads", settings)
        out = "\n".join(echoed)

        assert settings.auto_approve_reads is True
        assert "ON" in out
        # Persists across reload.
        assert CLISettings.load().auto_approve_reads is True

    def test_unknown_gate_lists_valid_options(self, tmp_path, monkeypatch):
        settings_file = tmp_path / "cli_settings.json"
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", settings_file)

        echoed: list[str] = []
        monkeypatch.setattr(
            "hosts.cli.__main__._echo",
            lambda text="", nl=True: echoed.append(text),
        )

        from hosts.cli.__main__ import _handle_permissions_command
        from hosts.cli.settings import CLISettings

        _handle_permissions_command("/permissions nonsense", CLISettings())
        out = "\n".join(echoed).lower()
        assert "unknown" in out
        assert "yolo" in out  # valid options listed
        assert "reads" in out

    def test_yolo_alias_toggles_existing_field(self, tmp_path, monkeypatch):
        # /permissions yolo should map to yolo_enabled — same field
        # /yolo toggles, just exposed through the unified UI.
        settings_file = tmp_path / "cli_settings.json"
        monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", settings_file)

        monkeypatch.setattr("hosts.cli.__main__._echo", lambda text="", nl=True: None)

        from hosts.cli.__main__ import _handle_permissions_command
        from hosts.cli.settings import CLISettings

        settings = CLISettings()
        _handle_permissions_command("/permissions yolo", settings)
        assert settings.yolo_enabled is True
        assert CLISettings.load().yolo_enabled is True


class TestExecutorEmitsInputRequiredOnConfirmOrder:
    """``HephaestusAgentExecutor`` must call ``send_input_required`` with the
    parsed read-back when ``determine_pipeline`` returns CONFIRM_ORDER."""

    @pytest.mark.asyncio
    async def test_clear_tier_emits_input_required_with_read_back(self):
        from agents.hephaestus.agent_executor import HephaestusAgentExecutor

        executor = HephaestusAgentExecutor()
        ctx = MagicMock()
        ctx.get_user_input.return_value = "add double(n)"
        task = MagicMock()
        task.context_id = "ctx-1"
        task.id = "task-1"
        updater = MagicMock()
        updater.add_artifact = AsyncMock()
        updater.complete = AsyncMock()
        updater.update_status = AsyncMock()

        send_input_calls: list = []

        async def fake_send_input_required(updater, task, message):
            send_input_calls.append(message)

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                new_callable=AsyncMock,
                return_value=(
                    'CONFIRM_ORDER: clear "double(n) in src/math.py with a test. Light the forge?"'
                ),
            ),
            patch(
                "agents.hephaestus.agent_executor.send_input_required",
                side_effect=fake_send_input_required,
            ),
            patch("agents.hephaestus.agent_executor.send_working_status"),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        assert len(send_input_calls) == 1
        message = send_input_calls[0]
        assert "double(n)" in message
        assert "Light the forge?" in message

    @pytest.mark.asyncio
    async def test_pipeline_does_not_run_after_confirm_order(self):
        from agents.hephaestus.agent_executor import HephaestusAgentExecutor

        executor = HephaestusAgentExecutor()
        ctx = MagicMock()
        ctx.get_user_input.return_value = "add double(n)"
        task = MagicMock()
        task.context_id = "ctx-1"
        task.id = "task-1"
        updater = MagicMock()
        updater.add_artifact = AsyncMock()
        updater.complete = AsyncMock()
        updater.update_status = AsyncMock()

        execute_pipeline_called = False

        async def fake_execute_pipeline(*args, **kwargs):
            nonlocal execute_pipeline_called
            execute_pipeline_called = True
            if False:
                yield None  # async generator

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                new_callable=AsyncMock,
                return_value='CONFIRM_ORDER: clear "x?"',
            ),
            patch(
                "agents.hephaestus.agent_executor.execute_pipeline",
                side_effect=fake_execute_pipeline,
            ),
            patch("agents.hephaestus.agent_executor.send_input_required"),
            patch("agents.hephaestus.agent_executor.send_working_status"),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        # The whole point of the gate — pipeline does NOT start until
        # the player has confirmed.
        assert execute_pipeline_called is False

    @pytest.mark.asyncio
    async def test_smart_tier_passes_through(self):
        from agents.hephaestus.agent_executor import HephaestusAgentExecutor

        executor = HephaestusAgentExecutor()
        ctx = MagicMock()
        ctx.get_user_input.return_value = "add divide function"
        task = MagicMock()
        task.context_id = "ctx-1"
        task.id = "task-1"
        updater = MagicMock()
        updater.add_artifact = AsyncMock()
        updater.complete = AsyncMock()
        updater.update_status = AsyncMock()

        send_input_calls: list = []

        async def fake_send_input_required(updater, task, message):
            send_input_calls.append(message)

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                new_callable=AsyncMock,
                return_value=(
                    'CONFIRM_ORDER: smart "divide(a, b) in src/math.py — '
                    'Metis flags zero-division. Bare or works?"'
                ),
            ),
            patch(
                "agents.hephaestus.agent_executor.send_input_required",
                side_effect=fake_send_input_required,
            ),
            patch("agents.hephaestus.agent_executor.send_working_status"),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        assert len(send_input_calls) == 1
        message = send_input_calls[0]
        assert "divide" in message
        assert "Bare or works" in message

    @pytest.mark.asyncio
    async def test_executor_message_carries_hephaestus_emoji_prefix(self):
        # The host's _maidenify_status detector keys off the leading agent
        # emoji to render a comms window. The executor must prefix the
        # read-back so the existing pipeline picks it up — no separate
        # "confirmation card" function needed in the CLI.
        from agents.hephaestus.agent_executor import HephaestusAgentExecutor

        executor = HephaestusAgentExecutor()
        ctx = MagicMock()
        ctx.get_user_input.return_value = "add x"
        task = MagicMock()
        task.context_id = "ctx-1"
        task.id = "task-1"
        updater = MagicMock()
        updater.add_artifact = AsyncMock()
        updater.complete = AsyncMock()
        updater.update_status = AsyncMock()

        send_input_calls: list = []

        async def fake_send_input_required(updater, task, message):
            send_input_calls.append(message)

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                new_callable=AsyncMock,
                return_value='CONFIRM_ORDER: clear "x?"',
            ),
            patch(
                "agents.hephaestus.agent_executor.send_input_required",
                side_effect=fake_send_input_required,
            ),
            patch("agents.hephaestus.agent_executor.send_working_status"),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        assert len(send_input_calls) == 1
        # \U0001f525 is the Hephaestus emoji; AGENT_EMOJI["hephaestus"].
        assert send_input_calls[0].startswith("\U0001f525")

    @pytest.mark.asyncio
    async def test_smart_tier_appends_metis_hint(self):
        from agents.hephaestus.agent_executor import HephaestusAgentExecutor

        executor = HephaestusAgentExecutor()
        ctx = MagicMock()
        ctx.get_user_input.return_value = "add divide"
        task = MagicMock()
        task.context_id = "ctx-1"
        task.id = "task-1"
        updater = MagicMock()
        updater.add_artifact = AsyncMock()
        updater.complete = AsyncMock()
        updater.update_status = AsyncMock()

        send_input_calls: list = []

        async def fake_send_input_required(updater, task, message):
            send_input_calls.append(message)

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                new_callable=AsyncMock,
                return_value='CONFIRM_ORDER: smart "divide(a, b). Bare or works?"',
            ),
            patch(
                "agents.hephaestus.agent_executor.send_input_required",
                side_effect=fake_send_input_required,
            ),
            patch("agents.hephaestus.agent_executor.send_working_status"),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        # Metis hint trails on smart tier so the player knows the
        # architectural muttering was a hint, not the spec.
        assert "Metis" in send_input_calls[0]

    @pytest.mark.asyncio
    async def test_clarify_tier_appends_cooling_hint(self):
        from agents.hephaestus.agent_executor import HephaestusAgentExecutor

        executor = HephaestusAgentExecutor()
        ctx = MagicMock()
        ctx.get_user_input.return_value = "speed it up"
        task = MagicMock()
        task.context_id = "ctx-1"
        task.id = "task-1"
        updater = MagicMock()
        updater.add_artifact = AsyncMock()
        updater.complete = AsyncMock()
        updater.update_status = AsyncMock()

        send_input_calls: list = []

        async def fake_send_input_required(updater, task, message):
            send_input_calls.append(message)

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                new_callable=AsyncMock,
                return_value='CONFIRM_ORDER: clarify "Which functions?"',
            ),
            patch(
                "agents.hephaestus.agent_executor.send_input_required",
                side_effect=fake_send_input_required,
            ),
            patch("agents.hephaestus.agent_executor.send_working_status"),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        # Clarify tier should signal "the forge is paused waiting for you"
        # so the player doesn't think it's still working.
        assert "Forge cools" in send_input_calls[0] or "cools" in send_input_calls[0]

    @pytest.mark.asyncio
    async def test_malformed_confirm_order_falls_through_to_pipeline(self):
        # If the parser can't decode the CONFIRM_ORDER token (LLM
        # got the format wrong), don't crash the player's request —
        # log the parse error and proceed with whatever default
        # pipeline behaviour exists. We still don't want to silently
        # ship code without confirmation, so the safest fallback is
        # "treat as ASK_USER" — surface to the player.
        from agents.hephaestus.agent_executor import HephaestusAgentExecutor

        executor = HephaestusAgentExecutor()
        ctx = MagicMock()
        ctx.get_user_input.return_value = "add double(n)"
        task = MagicMock()
        task.context_id = "ctx-1"
        task.id = "task-1"
        updater = MagicMock()
        updater.add_artifact = AsyncMock()
        updater.complete = AsyncMock()
        updater.update_status = AsyncMock()

        send_input_calls: list = []

        async def fake_send_input_required(updater, task, message):
            send_input_calls.append(message)

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                new_callable=AsyncMock,
                return_value="CONFIRM_ORDER: garbage with no quotes",
            ),
            patch(
                "agents.hephaestus.agent_executor.send_input_required",
                side_effect=fake_send_input_required,
            ),
            patch("agents.hephaestus.agent_executor.send_working_status"),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        # Fail-safe: don't run pipeline; surface a generic confirmation
        # ask to the player. The exact message doesn't matter — what
        # matters is we don't auto-execute on a malformed token.
        assert len(send_input_calls) == 1
