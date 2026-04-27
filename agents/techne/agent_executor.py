"""A2A bridge for Techne — translates between A2A protocol and coder agent logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from a2a.types import DataPart, Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.techne.agent import (
    apply_code_changes,
    get_git_context,
    parse_file_paths,
    read_files,
)
from kourai_common.a2a_utils import extract_image_parts, parse_project_root
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.mcp_client import kourai_project_root_var
from kourai_common.messaging import send_working_status
from kourai_common.player import PlayerProfile
from kourai_common.stack import looks_like_scaffolding
from kourai_common.tracing import create_span
from kourai_common.virtues import update_virtue

_MUTATING_TOOLS = frozenset({"write_file", "edit_file", "delete_file"})

if TYPE_CHECKING:
    from a2a.server.agent_execution import RequestContext
    from a2a.server.events import EventQueue
    from a2a.server.tasks import TaskUpdater

log = logging.getLogger(__name__)


class TechneAgentExecutor(BaseAgentExecutor):
    """A2A executor for the Techne coder agent."""

    def get_input_required_message(self) -> str:
        return (
            "I need a coding task. Tell me what to implement, "
            "fix, or modify — ideally with file paths."
        )

    @executor_error_handler(agent_name="techne")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Delegate to base class which calls execute_agent_logic
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        """Techne-specific: generate code changes from task description."""
        with create_span("techne.execute", {"a2a.method": "execute"}):
            user_input = context.get_user_input()
            project_root = parse_project_root(user_input)
            kourai_project_root_var.set(project_root)

            # Step 1: Parse file paths from the request
            file_paths = parse_file_paths(user_input)

            await send_working_status(
                updater,
                task,
                "Reading existing code..." + (f" ({len(file_paths)} files)" if file_paths else ""),
            )

            # Step 2: Read existing files for context
            file_contents = {}
            if file_paths:
                with create_span("techne.read_files", {"count": str(len(file_paths))}):
                    file_contents = await read_files(file_paths)

            # Step 2b: Load template reference files for new project scaffolding
            if looks_like_scaffolding(user_input):
                backend_templates = [
                    "templates/backend/pyproject.toml",
                    "templates/backend/src/app/main.py",
                    "templates/backend/src/app/models.py",
                    "templates/backend/tests/conftest.py",
                ]
                frontend_templates = [
                    "templates/frontend/package.json",
                    "templates/frontend/src/App.tsx",
                ]
                lower = user_input.lower()
                paths: list[str] = []
                if "frontend" in lower or "react" in lower or "full" in lower:
                    paths.extend(frontend_templates)
                if "backend" in lower or "api" in lower or "full" in lower:
                    paths.extend(backend_templates)
                # Default to both if neither side is specified
                if not paths:
                    paths = backend_templates + frontend_templates
                with create_span("techne.read_templates"):
                    templates = await read_files(paths)
                    file_contents.update(templates)

            # Step 3: Get git context — stream output. Round 6 caught
            # `git status --short` exiting 128 because the specialist
            # container's default cwd (`/app`) isn't the worktree;
            # threading the parsed project_root through fixes it.
            async def _git_status(line: str) -> None:
                await send_working_status(updater, task, line, emoji="🔍")

            with create_span("techne.git_context"):
                git_context = await get_git_context(
                    cwd=str(project_root), status_callback=_git_status
                )

            await send_working_status(
                updater,
                task,
                "Generating code changes...",
            )

            async def _on_tool(name: str, args: dict, result: str) -> None:
                target = args.get("path", "")
                ok = "ok" if not result.startswith("ERROR:") else "fail"
                await send_working_status(updater, task, f"{name} {target} ({ok})", emoji="🔧")

            # Step 4: Drive the agentic tool-use loop. Each tool call writes
            # directly to disk via FORGE_TOOL_HANDLERS — no regex parse.
            with create_span("techne.tool_loop", {"task": user_input[:100]}):
                result, tool_log = await apply_code_changes(
                    task_description=user_input,
                    project_root=project_root,
                    file_contents=file_contents,
                    git_context=git_context,
                    image_parts=extract_image_parts(context) or None,
                    context_id=task.context_id,
                    on_tool_call=_on_tool,
                )

            fixes_applied = sum(
                1
                for entry in tool_log
                if entry["name"] in _MUTATING_TOOLS and not entry["result"].startswith("ERROR:")
            )

            await send_working_status(
                updater,
                task,
                f"Applied {fixes_applied} code changes to disk",
            )

            # Step 6: Emit both human-readable text and machine-readable structured data
            await updater.add_artifact(
                [
                    Part(root=TextPart(text=result)),
                    Part(
                        root=DataPart(
                            data={
                                "files_read": len(file_contents),
                                "files_changed": fixes_applied,
                                "file_paths": file_paths,
                                "tool_calls": [
                                    {"name": e["name"], "args": e["args"]} for e in tool_log
                                ],
                            }
                        )
                    ),
                ],
                name="code_changes",
            )
            await updater.complete()
            log.info(
                "Techne completed — %d tool calls, %d successful writes",
                len(tool_log),
                fixes_applied,
            )

            # Virtue update: successful code writes → arete (excellence-seeking)
            if fixes_applied > 0:
                _profile = PlayerProfile.load()
                if _profile:
                    update_virtue(_profile.player_id, "arete", 0.01 * min(fixes_applied, 5))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
