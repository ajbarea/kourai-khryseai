"""M3 — per-tool-call status streaming for Kallos and Dokimasia.

Techne already ships per-tool-call status via the ``on_tool_call`` callback
that ``chat_with_tools`` invokes inside the agentic loop. M3 closes the
gap for the other two specialists that drive ``chat_with_tools`` —
Kallos's lint-fix loop and Dokimasia's test-fix loop — so the player
sees each ``write_file``/``edit_file`` land live instead of staring at a
black box during the fix step.

These tests assert the wiring at two layers:

1. ``apply_lint_fixes`` / ``apply_test_fixes`` accept ``on_tool_call`` and
   forward it verbatim to ``chat_with_tools`` (no swallowing).
2. The Kallos and Dokimasia executors wire an ``_on_tool`` closure that
   pushes one ``send_working_status`` call per tool execution.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@asynccontextmanager
async def _fake_forge_bridge(*_args, **_kwargs):
    """Stub `forge_tool_bridge` so M2 Change 3b/c migration tests don't
    launch the `kourai-mcp-forge` subprocess. The chat_with_tools mock
    under each test inspects the wired callback shape independently.
    """
    from kourai_common.mcp_bridge import MCPToolBridge

    yield MCPToolBridge(tools=[], tool_handlers={})


class TestApplyLintFixesForwardsCallback:
    """Kallos's apply_lint_fixes is the boundary between executor and LLM loop."""

    @pytest.mark.asyncio
    async def test_on_tool_call_passed_to_chat_with_tools(self, tmp_path):
        from agents.kallos.agent import apply_lint_fixes

        async def my_callback(name, args, result):
            pass

        with (
            patch("agents.kallos.agent.forge_tool_bridge", _fake_forge_bridge),
            patch(
                "agents.kallos.agent.chat_with_tools",
                new_callable=AsyncMock,
                return_value=("done", []),
            ) as mock_chat,
        ):
            await apply_lint_fixes(
                lint_output="ruff: E501",
                file_paths=set(),
                project_root=tmp_path,
                context_id="ctx-1",
                on_tool_call=my_callback,
            )

        assert mock_chat.await_count == 1
        assert mock_chat.await_args is not None  # narrow `_Call | None` for ty
        kwargs = mock_chat.await_args.kwargs
        assert kwargs["on_tool_call"] is my_callback

    @pytest.mark.asyncio
    async def test_default_callback_is_none(self, tmp_path):
        from agents.kallos.agent import apply_lint_fixes

        with (
            patch("agents.kallos.agent.forge_tool_bridge", _fake_forge_bridge),
            patch(
                "agents.kallos.agent.chat_with_tools",
                new_callable=AsyncMock,
                return_value=("done", []),
            ) as mock_chat,
        ):
            await apply_lint_fixes(
                lint_output="",
                file_paths=set(),
                project_root=tmp_path,
                context_id="ctx-1",
            )

        assert mock_chat.await_args is not None  # narrow `_Call | None` for ty
        assert mock_chat.await_args.kwargs["on_tool_call"] is None


class TestApplyTestFixesForwardsCallback:
    """Same boundary in Dokimasia's test-fix loop."""

    @pytest.mark.asyncio
    async def test_on_tool_call_passed_to_chat_with_tools(self, tmp_path):
        from agents.dokimasia.agent import apply_test_fixes

        async def my_callback(name, args, result):
            pass

        with (
            patch("agents.dokimasia.agent.forge_tool_bridge", _fake_forge_bridge),
            patch(
                "agents.dokimasia.agent.chat_with_tools",
                new_callable=AsyncMock,
                return_value=("done", []),
            ) as mock_chat,
        ):
            await apply_test_fixes(
                pytest_output="FAILED tests/test_x.py::test_y",
                file_paths=set(),
                project_root=tmp_path,
                context_id="ctx-1",
                on_tool_call=my_callback,
            )

        assert mock_chat.await_args is not None  # narrow `_Call | None` for ty
        assert mock_chat.await_args.kwargs["on_tool_call"] is my_callback

    @pytest.mark.asyncio
    async def test_default_callback_is_none(self, tmp_path):
        from agents.dokimasia.agent import apply_test_fixes

        with (
            patch("agents.dokimasia.agent.forge_tool_bridge", _fake_forge_bridge),
            patch(
                "agents.dokimasia.agent.chat_with_tools",
                new_callable=AsyncMock,
                return_value=("done", []),
            ) as mock_chat,
        ):
            await apply_test_fixes(
                pytest_output="",
                file_paths=set(),
                project_root=tmp_path,
                context_id="ctx-1",
            )

        assert mock_chat.await_args is not None  # narrow `_Call | None` for ty
        assert mock_chat.await_args.kwargs["on_tool_call"] is None


class TestKallosExecutorEmitsToolCallStatus:
    """The KallosAgentExecutor wraps apply_lint_fixes with a callback that
    pushes one send_working_status per tool execution."""

    @pytest.mark.asyncio
    async def test_on_tool_invokes_send_working_status_with_kallos_emoji(self, tmp_path):
        from agents.kallos import agent_executor as kallos_executor_module

        captured_callback: dict = {}
        captured_status_calls: list = []

        async def fake_apply_lint_fixes(
            lint_output, files, project_root, ctx_id, on_tool_call=None
        ):
            captured_callback["fn"] = on_tool_call
            return 0

        async def fake_send_working_status(updater, task, message, emoji="⚙️"):
            captured_status_calls.append((message, emoji))

        with (
            patch.object(
                kallos_executor_module,
                "send_working_status",
                side_effect=fake_send_working_status,
            ),
            patch(
                "agents.kallos.agent.apply_lint_fixes",
                side_effect=fake_apply_lint_fixes,
            ),
        ):
            updater = MagicMock()
            updater.add_artifact = AsyncMock()
            updater.complete = AsyncMock()
            updater.update_status = AsyncMock()
            task = MagicMock()
            task.context_id = "ctx-1"

            executor = kallos_executor_module.KallosAgentExecutor()
            project_root = str(tmp_path)
            run_make_lint_calls: list = []

            async def fake_run_make_lint(cwd=None, status_callback=None):
                run_make_lint_calls.append(cwd)
                return False, "ruff: tests/test_x.py:1:1: E501"

            extract_files_called: list = []

            async def fake_apply_fixes_wrapper(lint_output, files, ctx_id):
                # Re-create what run_fix_loop does: invoke our wrapper, which
                # closes over _on_tool, and forward the call.
                from agents.kallos.agent import apply_lint_fixes

                return await apply_lint_fixes(
                    lint_output, files, project_root, ctx_id, on_tool_call=None
                )

            # Drive the wrapper that the executor sets up: stand up a fake
            # run_fix_loop that calls apply_fixes once and then calls the
            # captured callback to simulate a tool execution.
            async def fake_run_fix_loop(
                tool_name,
                run_tool,
                extract_files,
                apply_fixes,
                updater,
                task,
                emoji="✨",
                max_iterations=3,
                messages=None,
            ):
                extract_files_called.append(tool_name)
                # Call the apply_fixes wrapper with empty file set
                await apply_fixes("ruff: E501", set(), "ctx-1")
                # Now simulate a tool execution by invoking the captured callback.
                callback = captured_callback.get("fn")
                assert callback is not None, "executor never wired on_tool_call"
                await callback(
                    "edit_file",
                    {"path": "src/foo.py", "old_string": "x", "new_string": "y"},
                    "Edited src/foo.py",
                )
                # Result tuple shape: (all_clean, final_output, FixLoopResult-ish)
                fake_result = MagicMock()
                fake_result.to_dict.return_value = {}
                return True, "All clean", fake_result

            with (
                patch(
                    "kourai_common.fix_loop.run_fix_loop",
                    side_effect=fake_run_fix_loop,
                ),
                patch(
                    "agents.kallos.agent.run_make_lint",
                    side_effect=fake_run_make_lint,
                ),
                patch(
                    "kourai_common.subprocess.extract_files_from_output",
                    return_value=set(),
                ),
                patch(
                    "agents.kallos.agent_executor.parse_project_root",
                    return_value=project_root,
                ),
                patch.object(kallos_executor_module, "create_span"),
                patch("agents.aidos.agent.flag_slop_words", return_value=[]),
                patch("agents.aidos.agent.analyze_slop", return_value="CLEAN"),
                patch("kourai_common.virtues.update_virtue"),
                patch(
                    "kourai_common.player.PlayerProfile.load",
                    return_value=None,
                ),
            ):
                ctx = MagicMock()
                ctx.get_user_input.return_value = f"[project_root: {project_root}]"
                await executor.execute_agent_logic(ctx, task, updater)

            tool_messages = [
                (msg, emoji)
                for (msg, emoji) in captured_status_calls
                if "edit_file" in msg or "write_file" in msg or "delete_file" in msg
            ]
            assert tool_messages, (
                f"executor never called send_working_status for a tool event: "
                f"{captured_status_calls}"
            )
            # Kallos's signature emoji
            assert tool_messages[0][1] == "✨"
            # Format: "<name> <path> (<status>)"
            assert "edit_file" in tool_messages[0][0]
            assert "src/foo.py" in tool_messages[0][0]
            assert "(ok)" in tool_messages[0][0]


class TestDokimasiaExecutorEmitsToolCallStatus:
    """Dokimasia's run-tests branch wraps apply_test_fixes with the same
    callback shape and emits with her signature emoji."""

    @pytest.mark.asyncio
    async def test_on_tool_invokes_send_working_status_with_dokimasia_emoji(self, tmp_path):
        from agents.dokimasia import agent_executor as dok_executor_module

        captured_callback: dict = {}
        captured_status_calls: list = []

        async def fake_send_working_status(updater, task, message, emoji="⚙️"):
            captured_status_calls.append((message, emoji))

        async def fake_apply_test_fixes(
            pytest_output, files, project_root, ctx_id, on_tool_call=None
        ):
            captured_callback["fn"] = on_tool_call
            return 0

        async def fake_run_fix_loop(
            tool_name,
            run_tool,
            extract_files,
            apply_fixes,
            updater,
            task,
            emoji="✨",
            max_iterations=3,
            messages=None,
        ):
            await apply_fixes("FAILED tests/test_x.py::test_y", set(), "ctx-1")
            callback = captured_callback.get("fn")
            assert callback is not None, "executor never wired on_tool_call"
            await callback(
                "write_file",
                {"path": "tests/test_x.py", "content": "def test_y(): pass"},
                "Wrote tests/test_x.py (20 chars).",
            )
            fake_result = MagicMock()
            fake_result.to_dict.return_value = {}
            return True, "All passed", fake_result

        mock_pytest_result = MagicMock()
        mock_pytest_result.success = False
        mock_pytest_result.output = "FAILED"

        with (
            patch.object(
                dok_executor_module,
                "send_working_status",
                side_effect=fake_send_working_status,
            ),
            patch(
                "agents.dokimasia.agent.apply_test_fixes",
                side_effect=fake_apply_test_fixes,
            ),
            patch(
                "kourai_common.fix_loop.run_fix_loop",
                side_effect=fake_run_fix_loop,
            ),
            patch(
                "agents.dokimasia.agent.run_pytest",
                return_value=mock_pytest_result,
            ),
            patch(
                "kourai_common.subprocess.extract_files_from_output",
                return_value=set(),
            ),
            patch.object(dok_executor_module, "create_span"),
            patch("kourai_common.virtues.update_virtue"),
            patch(
                "kourai_common.player.PlayerProfile.load",
                return_value=None,
            ),
        ):
            executor = dok_executor_module.DokimasiaAgentExecutor()
            ctx = MagicMock()
            ctx.get_user_input.return_value = f"[project_root: {tmp_path}] run tests"
            updater = MagicMock()
            updater.add_artifact = AsyncMock()
            updater.complete = AsyncMock()
            updater.update_status = AsyncMock()
            task = MagicMock()
            task.context_id = "ctx-1"

            await executor.execute_agent_logic(ctx, task, updater)

        tool_messages = [
            (msg, emoji)
            for (msg, emoji) in captured_status_calls
            if "write_file" in msg or "edit_file" in msg or "delete_file" in msg
        ]
        assert tool_messages, (
            f"executor never called send_working_status for a tool event: {captured_status_calls}"
        )
        assert tool_messages[0][1] == "🧪"
        assert "write_file" in tool_messages[0][0]
        assert "tests/test_x.py" in tool_messages[0][0]
        assert "(ok)" in tool_messages[0][0]


class TestErrorTagInToolMessage:
    """ERROR: results from forge tools render as ``(fail)`` so the player
    sees lint/test fixers stumbling without parsing the result string."""

    @pytest.mark.asyncio
    async def test_kallos_marks_failed_tool_call(self, tmp_path):
        from agents.kallos import agent_executor as kallos_executor_module

        captured_callback: dict = {}
        captured_status_calls: list = []

        async def fake_send_working_status(updater, task, message, emoji="⚙️"):
            captured_status_calls.append((message, emoji))

        async def fake_apply_lint_fixes(
            lint_output, files, project_root, ctx_id, on_tool_call=None
        ):
            captured_callback["fn"] = on_tool_call
            return 0

        async def fake_run_fix_loop(
            tool_name,
            run_tool,
            extract_files,
            apply_fixes,
            updater,
            task,
            emoji="✨",
            max_iterations=3,
            messages=None,
        ):
            await apply_fixes("ruff", set(), "ctx-1")
            callback = captured_callback.get("fn")
            assert callback is not None  # captured during apply_fixes; narrow Optional for ty
            await callback(
                "edit_file",
                {"path": "src/foo.py", "old_string": "x", "new_string": "y"},
                "ERROR: file not found",
            )
            fake_result = MagicMock()
            fake_result.to_dict.return_value = {}
            return True, "Done", fake_result

        async def fake_run_make_lint(cwd=None, status_callback=None):
            return False, "ruff: src/foo.py:1:1: F401"

        with (
            patch.object(
                kallos_executor_module,
                "send_working_status",
                side_effect=fake_send_working_status,
            ),
            patch(
                "agents.kallos.agent.apply_lint_fixes",
                side_effect=fake_apply_lint_fixes,
            ),
            patch(
                "kourai_common.fix_loop.run_fix_loop",
                side_effect=fake_run_fix_loop,
            ),
            patch(
                "agents.kallos.agent.run_make_lint",
                side_effect=fake_run_make_lint,
            ),
            patch(
                "kourai_common.subprocess.extract_files_from_output",
                return_value=set(),
            ),
            patch(
                "agents.kallos.agent_executor.parse_project_root",
                return_value=str(tmp_path),
            ),
            patch.object(kallos_executor_module, "create_span"),
            patch("agents.aidos.agent.flag_slop_words", return_value=[]),
            patch("agents.aidos.agent.analyze_slop", return_value="CLEAN"),
            patch("kourai_common.virtues.update_virtue"),
            patch(
                "kourai_common.player.PlayerProfile.load",
                return_value=None,
            ),
        ):
            executor = kallos_executor_module.KallosAgentExecutor()
            ctx = MagicMock()
            ctx.get_user_input.return_value = f"[project_root: {tmp_path}]"
            updater = MagicMock()
            updater.add_artifact = AsyncMock()
            updater.complete = AsyncMock()
            updater.update_status = AsyncMock()
            task = MagicMock()
            task.context_id = "ctx-1"

            await executor.execute_agent_logic(ctx, task, updater)

        fail_messages = [(msg, emoji) for (msg, emoji) in captured_status_calls if "(fail)" in msg]
        assert fail_messages, f"failed-tool-call status was never emitted: {captured_status_calls}"
        assert fail_messages[0][1] == "✨"
        assert "edit_file" in fail_messages[0][0]
