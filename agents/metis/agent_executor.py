"""A2A bridge for Metis — translates between A2A protocol and planner logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from a2a.types import DataPart, Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.metis.agent import create_spec_stream, get_project_context
from kourai_common.a2a_utils import extract_image_parts, parse_project_root
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.mcp_client import kourai_project_root_var
from kourai_common.messaging import send_input_required, send_working_status
from kourai_common.pause_state import stash_preference_kind
from kourai_common.pause_tag import extract_pause_tag
from kourai_common.projects import derive_project_id
from kourai_common.stack import get_stack_context, looks_like_scaffolding
from kourai_common.tracing import create_span

if TYPE_CHECKING:
    from a2a.server.agent_execution import RequestContext
    from a2a.server.events import EventQueue
    from a2a.server.tasks import TaskUpdater

log = logging.getLogger(__name__)


def _player_id_or_none() -> str | None:
    """Resolve the active player's UUID, or ``None`` when the profile is absent.

    Specialist containers may run without a player profile (CI, smoke
    tests, fresh installs). Recall is silently skipped in that case —
    the facts read path is fail-soft by design.
    """
    try:
        from kourai_common.player_profile import PlayerProfile
    except ImportError:  # pragma: no cover — narrow import-time guard
        return None
    profile = PlayerProfile.load()
    return profile.player_id if profile and profile.player_id else None


class MetisAgentExecutor(BaseAgentExecutor):
    """A2A executor for the Metis planner agent."""

    def get_input_required_message(self) -> str:
        return (
            "What feature or change do you want me to plan? "
            "Describe your idea and I'll create a detailed spec."
        )

    @executor_error_handler(agent_name="metis")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        """Metis-specific: create implementation specs."""
        with create_span("metis.execute", {"a2a.method": "execute"}):
            user_input = context.get_user_input()
            # The specialist container's default cwd (`/app`) isn't the
            # worktree, so `git status --short` exits 128 without `cwd=`
            # set. parse_project_root falls back to cwd when the
            # [project_root: ...] tag is missing, so internal / test
            # invocations are unaffected.
            project_root = parse_project_root(user_input)
            kourai_project_root_var.set(project_root)

            # Step 1: Gather project context
            await send_working_status(
                updater,
                task,
                "Analyzing project structure...",
                emoji="📐",
            )

            # Stream git output to player scratchpad for transparency
            async def _git_status(line: str) -> None:
                await send_working_status(updater, task, line, emoji="🔍")

            with create_span("metis.context"):
                project_context = await get_project_context(
                    project_root=str(project_root), status_callback=_git_status
                )

            # Inject default tech stack when scaffolding a new project
            if looks_like_scaffolding(user_input):
                project_context = (
                    f"=== DEFAULT TECH STACK ===\n{get_stack_context()}\n\n{project_context}"
                )

            # Step 2: Stream spec generation with inner-thought updates
            await send_working_status(
                updater,
                task,
                "Drafting implementation spec...",
                emoji="📐",
            )

            # M17 Phase 1 — load player + project identity for fact recall.
            # ``derive_project_id`` is a stable sha256-of-path so the same
            # project survives the player moving the repo on disk; the
            # tag-less internal-task fallback in ``parse_project_root``
            # returns ``Path.cwd()``, which we treat as global (None) here.
            player_id = _player_id_or_none()
            project_id_for_facts = (
                derive_project_id(project_root)
                if "[project_root:" in (user_input or "").lower()
                else None
            )

            with create_span("metis.spec", {"idea": user_input[:100]}):
                spec = ""
                chunk_count = 0
                async for chunk in create_spec_stream(
                    idea=user_input,
                    project_context=project_context,
                    image_parts=extract_image_parts(context) or None,
                    context_id=task.context_id,
                    player_id=player_id,
                    project_id=project_id_for_facts,
                ):
                    spec += chunk
                    chunk_count += 1
                    if chunk_count % 5 == 0:
                        lines = spec.strip().split("\n")
                        latest = lines[-1] if lines else ""
                        if len(latest) > 60:
                            latest = latest[:57] + "..."
                        if latest.strip():
                            await send_working_status(
                                updater, task, f"Planning: {latest}", emoji="📐"
                            )

            await send_working_status(
                updater,
                task,
                "Spec complete",
                emoji="📐",
            )

            # M17 Phase 1 — pull the trailing PAUSE tag, if Metis classified
            # the spec as gated on a one-time-per-project preference. The
            # parser fails closed on unknown kinds / malformed shapes, so
            # the spec ships normally when the LLM emits garbage.
            pause = extract_pause_tag(spec)
            artifact_text = pause.clean_text if pause else spec

            # Step 3: Emit both human-readable text and machine-readable structured data
            # Parse spec sections for downstream routing
            sections = [
                s.strip()
                for s in artifact_text.split("\n")
                if s.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7."))
            ]
            await updater.add_artifact(
                [
                    Part(root=TextPart(text=artifact_text)),
                    Part(
                        root=DataPart(
                            data={
                                "step_count": len(sections),
                                "has_file_list": "files to modify" in artifact_text.lower()
                                or "files to create" in artifact_text.lower(),
                                "has_tests": "testing" in artifact_text.lower(),
                                "preference_kind": pause.preference_kind if pause else None,
                            }
                        )
                    ),
                ],
                name="implementation_spec",
            )

            if pause:
                stash_preference_kind(task.context_id, pause.preference_kind)
                await send_input_required(updater, task, pause.question)
                log.info(
                    "Metis paused for %s preference — context=%s",
                    pause.preference_kind,
                    task.context_id,
                )
                return

            await updater.complete()
            log.info("Metis completed — spec generated (%d steps)", len(sections))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
