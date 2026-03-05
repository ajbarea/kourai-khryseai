"""Helpers for A2A task status updates — eliminates repetitive boilerplate."""

from __future__ import annotations

from a2a.server.tasks import TaskUpdater
from a2a.types import Task, TaskState
from a2a.utils import new_agent_text_message


async def send_working_status(
    updater: TaskUpdater,
    task: Task,
    message: str,
    emoji: str = "⚙️",
) -> None:
    """Send a working status update with optional emoji prefix.

    Args:
        updater: TaskUpdater instance for sending status
        task: Current task being executed
        message: Status message to display
        emoji: Emoji prefix (default: ⚙️)
    """
    await updater.update_status(
        TaskState.working,
        new_agent_text_message(
            f"{emoji} {message}",
            task.context_id,
            task.id,
        ),
    )


async def send_input_required(
    updater: TaskUpdater,
    task: Task,
    message: str,
) -> None:
    """Send input_required status and mark as final.

    Args:
        updater: TaskUpdater instance for sending status
        task: Current task being executed
        message: Message requesting user input
    """
    await updater.update_status(
        TaskState.input_required,
        new_agent_text_message(message, task.context_id, task.id),
        final=True,
    )


async def send_completed(
    updater: TaskUpdater,
    task: Task,
    message: str,
    emoji: str = "✅",
) -> None:
    """Send completed status with optional emoji prefix.

    Args:
        updater: TaskUpdater instance for sending status
        task: Current task being executed
        message: Completion message to display
        emoji: Emoji prefix (default: ✅)
    """
    await updater.update_status(
        TaskState.completed,
        new_agent_text_message(
            f"{emoji} {message}",
            task.context_id,
            task.id,
        ),
        final=True,
    )
