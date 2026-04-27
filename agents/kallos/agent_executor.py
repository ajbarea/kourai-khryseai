"""A2A bridge for Kallos — translates between A2A protocol and style agent logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from a2a.types import DataPart, Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.aidos.agent import analyze_slop, flag_slop_words
from kourai_common.a2a_utils import parse_project_root
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.mcp_client import kourai_project_root_var
from kourai_common.messaging import send_working_status
from kourai_common.player import PlayerProfile
from kourai_common.tracing import create_span
from kourai_common.virtues import update_virtue

if TYPE_CHECKING:
    from a2a.server.agent_execution import RequestContext
    from a2a.server.events import EventQueue
    from a2a.server.tasks import TaskUpdater

log = logging.getLogger(__name__)


class KallosAgentExecutor(BaseAgentExecutor):
    """A2A executor for the Kallos stylist agent."""

    def get_input_required_message(self) -> str:
        return (
            "I need a target path or file contents to analyze. "
            "Please provide a directory path or code to check."
        )

    @executor_error_handler(agent_name="kallos")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        """Kallos-specific: run linting and auto-fix issues."""
        with create_span("kallos.execute", {"a2a.method": "execute"}):
            from typing import Any

            from agents.kallos.agent import apply_lint_fixes, run_make_lint
            from kourai_common.fix_loop import KALLOS_MESSAGES, run_fix_loop
            from kourai_common.subprocess import extract_files_from_output

            async def _lint_status(line: str) -> None:
                await send_working_status(updater, task, line, emoji="💻")

            project_root = parse_project_root(context.get_user_input())
            kourai_project_root_var.set(project_root)

            async def _run_lint_with_status() -> tuple[bool, str]:
                return await run_make_lint(cwd=str(project_root), status_callback=_lint_status)

            async def _on_tool(name: str, args: dict[str, Any], result: str) -> None:
                target = args.get("path", "")
                ok = "ok" if not result.startswith("ERROR:") else "fail"
                await send_working_status(updater, task, f"{name} {target} ({ok})", emoji="✨")

            async def _apply_fixes(
                lint_output: str,
                files: set[str],
                ctx_id: str | None,
            ) -> int:
                return await apply_lint_fixes(
                    lint_output,
                    files,
                    project_root,
                    ctx_id,
                    on_tool_call=_on_tool,
                )

            all_clean, final_output, result = await run_fix_loop(
                tool_name="make lint",
                run_tool=_run_lint_with_status,
                extract_files=extract_files_from_output,
                apply_fixes=_apply_fixes,
                updater=updater,
                task=task,
                emoji="✨",
                messages=KALLOS_MESSAGES,
            )

            # Format final output
            if all_clean:
                final_output = "✨ All linting checks passed!\n\n" + final_output
            else:
                final_output = f"✨ Linting completed with issues.\n\n{final_output}"

            # Run Aidos slop detection on the fix output (comments/docstrings)
            slop_words = flag_slop_words(final_output)
            if slop_words:
                await send_working_status(
                    updater,
                    task,
                    f"Aidos: {len(slop_words)} slop word(s) found — {', '.join(slop_words[:3])}",
                    emoji="🚫",
                )
                slop_analysis = await analyze_slop(final_output, context_id=task.context_id)
                if slop_analysis != "CLEAN":
                    final_output += f"\n\n[Aidos — Language Review]\n{slop_analysis}"

            # Emit both human-readable text and machine-readable structured data
            await updater.add_artifact(
                [
                    Part(root=TextPart(text=final_output)),
                    Part(root=DataPart(data=result.to_dict())),
                ],
                name="style_report",
            )

            status = "all clean" if all_clean else "issues remain"
            await updater.complete()
            log.info("Kallos completed — %s", status)

            # Virtue update: clean lint pass → Techne (craft precision)
            _profile = PlayerProfile.load()
            if _profile:
                _delta = 0.01 if all_clean else 0.005
                update_virtue(_profile.player_id, "techne_v", _delta)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
