"""Helpers for A2A wire-shape construction.

Two surfaces:

* ``text_part`` / ``file_part_from_b64`` / ``data_part`` / ``user_message``
  centralize Part and Message construction so the eventual a2a-sdk 1.0
  cutover (M7 Phase 3) flips one helper module instead of every executor.
* ``send_working_status`` / ``send_input_required`` / ``send_completed``
  wrap ``TaskUpdater.update_status`` for executors so they don't repeat
  the same three-line boilerplate per status transition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from a2a.types import (
    DataPart,
    FilePart,
    FileWithBytes,
    Message,
    Part,
    Role,
    Task,
    TaskState,
    TextPart,
)
from a2a.utils import new_agent_text_message

if TYPE_CHECKING:
    from collections.abc import Sequence

    from a2a.server.tasks import TaskUpdater


# ── Part / Message construction (M7 Phase 1) ──────────────────────────


def text_part(text: str) -> Part:
    """Build an A2A text Part wrapping the given string."""
    return Part(root=TextPart(text=text))


def file_part_from_b64(
    b64_data: str,
    media_type: str,
    filename: str = "attachment",
) -> Part:
    """Build an A2A file Part from a base64-encoded payload.

    The 0.3 wire shape carries base64-encoded bytes in ``FileWithBytes.bytes``.
    Phase 3's flip to 1.0 will decode internally to feed ``Part(raw=...)`` —
    the helper API stays b64-string to keep CLI / GUI attachment loaders
    unchanged across the cutover.
    """
    return Part(
        root=FilePart(
            file=FileWithBytes(
                bytes=b64_data,
                mime_type=media_type,
                name=filename,
            )
        )
    )


def data_part(payload: dict[str, Any]) -> Part:
    """Build an A2A data Part wrapping the given dict."""
    return Part(root=DataPart(data=payload))


def user_message(
    text: str,
    *,
    context_id: str | None = None,
    task_id: str | None = None,
    message_id: str | None = None,
    extra_parts: Sequence[Part] | None = None,
) -> Message:
    """Build an A2A Message with role=user, a text body, and optional extra parts.

    Mirrors how hosts (CLI, GUI, vn_bridge) construct outbound prompts —
    one text Part with the user's typed input, optional FilePart(s) for
    attachments, optional context/task IDs for resume threading.
    """
    parts: list[Part] = [text_part(text)]
    if extra_parts:
        parts.extend(extra_parts)
    msg = Message(
        role=Role.user,
        parts=parts,
        message_id=message_id or str(uuid4()),
    )
    if context_id is not None:
        msg.context_id = context_id
    if task_id is not None:
        msg.task_id = task_id
    return msg


# ── Part inspection (M7 Phase 2) ──────────────────────────────────────


def is_file_part(part: Part) -> bool:
    """Return True if the Part carries embedded file bytes (FileWithBytes)."""
    root = part.root
    return isinstance(root, FilePart) and isinstance(root.file, FileWithBytes)


def get_file_bytes(part: Part) -> tuple[str, str]:
    """Extract (base64_bytes, media_type) from a file Part.

    Caller must ensure ``is_file_part(part)`` first.
    """
    file = part.root.file
    return file.bytes, file.mime_type or "image/png"


# ── Task status helpers ───────────────────────────────────────────────


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
