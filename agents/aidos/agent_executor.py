"""A2A executor for Aidos — anti-slop language enforcer."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from a2a.types import Task, UnsupportedOperationError

from agents.aidos.agent import analyze_slop, flag_slop_words, flag_vacuous_docstrings
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.messaging import data_part, send_working_status, text_part

if TYPE_CHECKING:
    from a2a.server.agent_execution import RequestContext
    from a2a.server.events import EventQueue
    from a2a.server.tasks import TaskUpdater

log = logging.getLogger(__name__)


class AidosAgentExecutor(BaseAgentExecutor):
    """A2A executor for Aidos."""

    def get_input_required_message(self) -> str:
        return "Give me the text to review for slop."

    @executor_error_handler(agent_name="aidos")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        user_input = context.get_user_input()

        # Fast pre-screen
        slop_words = flag_slop_words(user_input)
        vacuous = flag_vacuous_docstrings(user_input)
        issues: list[str] = []
        if slop_words:
            issues.append(f"{len(slop_words)} slop word(s): {', '.join(slop_words[:5])}")
        if vacuous:
            names = ", ".join(f"`{v['name']}`" for v in vacuous[:5])
            issues.append(f"{len(vacuous)} vacuous docstring(s): {names}")

        if issues:
            await send_working_status(updater, task, "Found " + "; ".join(issues), emoji="🚫")
        else:
            await send_working_status(updater, task, "Scanning for slop...", emoji="🔍")

        result = await analyze_slop(user_input, context_id=task.context_id)

        await updater.add_artifact(
            [
                text_part(result),
                data_part(
                    {
                        "slop_words_found": slop_words,
                        "vacuous_docstrings": [v["name"] for v in vacuous],
                        "clean": result == "CLEAN",
                    }
                ),
            ],
            name="aidos_analysis",
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise UnsupportedOperationError()
