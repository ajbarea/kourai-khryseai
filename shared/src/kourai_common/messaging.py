"""Helpers for A2A wire-shape construction.

Two surfaces:

* ``text_part`` / ``file_part_from_b64`` / ``data_part`` / ``user_message``
  centralize Part and Message construction. ``a2a-sdk`` 1.0 went
  protobuf-based — Part is a unified message with member-discriminated
  fields (``text``, ``raw``, ``url``, ``data``) instead of a tagged-union
  root, and discrimination is by ``part.HasField('text' | 'raw' |
  'url' | 'data')`` rather than ``isinstance`` on a wrapper. These
  helpers absorb the wire shape so executors don't see protobuf in
  their imports.
* ``send_working_status`` / ``send_input_required`` / ``send_completed``
  wrap ``TaskUpdater`` lifecycle methods (``start_work`` /
  ``requires_input`` / ``complete``) for executors so they don't repeat
  the same three-line boilerplate per status transition.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from a2a.helpers import new_text_message
from a2a.types import Message, Part, Role

if TYPE_CHECKING:
    from collections.abc import Sequence

    from a2a.server.tasks import TaskUpdater
    from a2a.types import Task


# ── Part / Message construction ───────────────────────────────────────


def text_part(text: str) -> Part:
    """Build an A2A text Part wrapping the given string."""
    return Part(text=text)


def file_part_from_b64(
    b64_data: str,
    media_type: str,
    filename: str = "attachment",
) -> Part:
    """Build an A2A file Part from a base64-encoded payload.

    Caller passes the b64-encoded string (matching how CLI / GUI
    attachment loaders carry images). The 1.0 wire shape stores raw
    bytes, so we decode internally.
    """
    raw = base64.b64decode(b64_data) if b64_data else b""
    return Part(raw=raw, media_type=media_type, filename=filename)


def data_part(payload: dict[str, Any]) -> Part:
    """Build an A2A data Part wrapping the given dict.

    The 1.0 wire shape stores the dict as a ``google.protobuf.struct_pb2.Value``;
    callers and downstream readers operate on plain dicts via
    ``data_part_to_dict``.
    """
    from google.protobuf.json_format import ParseDict
    from google.protobuf.struct_pb2 import Value  # ty: ignore[unresolved-import]

    return Part(data=ParseDict(payload, Value()))


def data_part_to_dict(part: Part) -> dict[str, Any]:
    """Recover the dict payload from a data Part built with ``data_part``."""
    from google.protobuf.json_format import MessageToDict

    return MessageToDict(part.data)


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
    msg = new_text_message(text, role=Role.ROLE_USER)
    if extra_parts:
        msg.parts.extend(extra_parts)
    msg.message_id = message_id or str(uuid4())
    if context_id is not None:
        msg.context_id = context_id
    if task_id is not None:
        msg.task_id = task_id
    return msg


# ── Part inspection ───────────────────────────────────────────────────


def is_file_part(part: Part) -> bool:
    """Return True if the Part carries embedded file bytes."""
    return part.HasField("raw")


def get_file_bytes(part: Part) -> tuple[str, str]:
    """Extract (base64_bytes, media_type) from a file Part.

    Caller must ensure ``is_file_part(part)`` first. Re-encodes the raw
    bytes as base64 so downstream LiteLLM / data-URL consumers receive
    the same shape they did under 0.3 ``FileWithBytes``.
    """
    b64 = base64.b64encode(part.raw).decode("ascii") if part.raw else ""
    return b64, part.media_type or "image/png"


# ── Task status helpers ───────────────────────────────────────────────


async def send_working_status(
    updater: TaskUpdater,
    task: Task,
    message: str,
    emoji: str = "⚙️",
) -> None:
    """Send a working status update with optional emoji prefix."""
    msg = updater.new_agent_message(parts=[text_part(f"{emoji} {message}")])
    await updater.start_work(message=msg)


async def send_input_required(
    updater: TaskUpdater,
    task: Task,
    message: str,
) -> None:
    """Request user input and mark the task as paused."""
    msg = updater.new_agent_message(parts=[text_part(message)])
    await updater.requires_input(message=msg)


async def send_completed(
    updater: TaskUpdater,
    task: Task,
    message: str,
    emoji: str = "✅",
) -> None:
    """Mark the task as completed with a final status message."""
    msg = updater.new_agent_message(parts=[text_part(f"{emoji} {message}")])
    await updater.complete(message=msg)
