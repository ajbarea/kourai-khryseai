"""Helpers for A2A wire-shape construction.

Three surfaces:

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
* ``KIND_*`` constants + ``set_content_kind`` / ``get_content_kind`` +
  ``kind_message`` carry M18's content-kind discriminator on
  ``Message.metadata`` so the host routes by metadata kind rather than
  prose-parsing emoji prefixes. The four kinds (dialogue / status / code
  / spec) split TTS-eligible from visual-only content and let status
  events fire-and-render without gating the next event on narration.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any, Final, Literal
from uuid import uuid4

from a2a.helpers import new_text_message
from a2a.types import (
    Message,
    Part,
    Role,
    SendMessageRequest,
    StreamResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
)

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
    metadata: dict[str, Any] | None = None,
) -> Message:
    """Build an A2A Message with role=user, a text body, and optional extra parts.

    Mirrors how hosts (CLI, GUI, vn_bridge) construct outbound prompts —
    one text Part with the user's typed input, optional FilePart(s) for
    attachments, optional context/task IDs for resume threading, and
    optional ``Message.metadata`` for forge context (``project_root``,
    ``project_id``, ``yolo``, ``auto_approve_reads``,
    ``relationship_tiers``).
    """
    msg = new_text_message(text, role=Role.ROLE_USER)
    if extra_parts:
        msg.parts.extend(extra_parts)
    msg.message_id = message_id or str(uuid4())
    if context_id is not None:
        msg.context_id = context_id
    if task_id is not None:
        msg.task_id = task_id
    if metadata:
        for key, value in metadata.items():
            if value is None:
                continue
            msg.metadata[key] = value
    return msg


# ── Content-kind metadata (M18) ───────────────────────────────────────


ContentKind = Literal["dialogue", "status", "code", "spec"]
"""Discriminator for what an emitted Part carries — drives host routing.

* ``dialogue`` — TTS-eligible maiden speech rendered in a comms window;
  blocks the next event on narration completion.
* ``status`` — visual-only pipeline status (``Analyzing request...``,
  ``Pipeline: foo -> bar``); never spoken, never gates the next event.
* ``code`` — monospace body (diffs, command output) rendered without
  TTS or gating.
* ``spec`` — wide markdown render (specs, plans) without TTS or gating.
"""

KIND_DIALOGUE: Final[ContentKind] = "dialogue"
KIND_STATUS: Final[ContentKind] = "status"
KIND_CODE: Final[ContentKind] = "code"
KIND_SPEC: Final[ContentKind] = "spec"

KOURAI_KIND_METADATA_KEY: Final[str] = "kourai.streaming.content_kind"
"""Flat dotted ``Message.metadata`` key for the content-kind discriminator.

The A2A 1.0 spec recommends URI-namespaced extension keys for cross-vendor
extensibility (e.g. ``"https://example.com/extensions/geolocation/v1"``).
Kourai is internal-only — the agent fleet and the kourai-shipped hosts
are the only producers and consumers of this key — so a short dotted
namespace matches the existing forge-metadata pattern (``project_id``,
``project_root``, ``yolo``) and keeps each emission cheap. If kourai
ever publishes the streaming contract for external A2A agents to
consume, swap this constant to a URI; nothing else changes.
"""


def set_content_kind(message: Message, kind: ContentKind) -> None:
    """Tag a Message with its content-kind discriminator."""
    message.metadata[KOURAI_KIND_METADATA_KEY] = kind


def get_content_kind(message: Message | None) -> ContentKind | None:
    """Read the content-kind discriminator from a Message, or ``None`` if absent.

    Returns ``None`` for unmigrated specialists that emit without the
    metadata tag — the host falls back to the legacy emoji-prefix
    detection in that case. Unknown kind values also return ``None`` so
    the host can route them through the legacy path until the producer
    is updated.
    """
    if message is None:
        return None
    metadata = getattr(message, "metadata", None)
    if metadata is None:
        return None
    try:
        raw = metadata[KOURAI_KIND_METADATA_KEY]
    except (KeyError, TypeError, ValueError):
        # protobuf ``Struct.__getitem__`` raises ``ValueError`` ("Value not
        # set") when the key is absent or its inner ``Value`` oneof is
        # unset; plain dicts raise ``KeyError``. Both mean "not tagged."
        return None
    if raw in ("dialogue", "status", "code", "spec"):
        return raw  # type: ignore[return-value]
    return None


def kind_message(
    text: str,
    kind: ContentKind,
    *,
    role: Role = Role.ROLE_AGENT,
    context_id: str | None = None,
    task_id: str | None = None,
    message_id: str | None = None,
    extra_parts: Sequence[Part] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Message:
    """Build a Message tagged with a content-kind discriminator.

    Mirrors ``user_message`` but defaults to ``ROLE_AGENT`` since the
    typical caller is a specialist's executor emitting status/dialogue.
    The kind is stored under ``KOURAI_KIND_METADATA_KEY`` in
    ``Message.metadata`` alongside any caller-supplied metadata.

    Most agents won't construct messages directly — they go through
    ``send_working_status`` / ``send_input_required`` / ``send_completed``
    which now accept a ``kind`` kwarg. This builder is the underlying
    primitive for paths that need a tagged Message without the
    ``TaskUpdater`` lifecycle wrappers (e.g. ``add_artifact`` payloads,
    direct host emissions for tests).
    """
    msg = new_text_message(text, role=role)
    if extra_parts:
        msg.parts.extend(extra_parts)
    msg.message_id = message_id or str(uuid4())
    if context_id is not None:
        msg.context_id = context_id
    if task_id is not None:
        msg.task_id = task_id
    if metadata:
        for key, value in metadata.items():
            if value is None:
                continue
            msg.metadata[key] = value
    set_content_kind(msg, kind)
    return msg


def send_request(message: Message) -> SendMessageRequest:
    """Wrap an A2A Message in a SendMessageRequest for v1.0 ``client.send_message``.

    SDK 1.0's ``Client.send_message`` is typed as taking ``SendMessageRequest``;
    its ``_apply_client_config`` reaches into ``request.configuration`` for
    polling / push-notification / accepted-output-modes wiring. Passing a
    bare ``Message`` raises ``AttributeError: configuration`` because the
    Message proto has no such field. This helper is the one place callers
    construct the wrapper so the v0.3 → v1.0 boundary stays in one file.
    """
    return SendMessageRequest(message=message)


def stream_event(
    response: StreamResponse,
) -> Message | TaskStatusUpdateEvent | TaskArtifactUpdateEvent | Task:
    """Decode a v1.0 ``StreamResponse`` into its inner event payload.

    SDK 1.0's streaming ``send_message`` yields ``StreamResponse`` protos
    with a oneof payload (``message`` / ``task`` / ``status_update`` /
    ``artifact_update``). v0.3 yielded ``Message`` objects or
    ``(Task, update | None)`` tuples directly; consumers typed the dispatch
    around ``isinstance``. This helper returns the inner event so the
    ``isinstance``-based dispatch keeps working — without it, every caller
    has to repeat ``HasField`` chains.

    Final task snapshots (no streaming update) come back as ``Task``;
    consumers that distinguished them via ``update is None`` should match
    on ``isinstance(event, Task)`` instead.
    """
    if response.HasField("message"):
        return response.message
    if response.HasField("status_update"):
        return response.status_update
    if response.HasField("artifact_update"):
        return response.artifact_update
    if response.HasField("task"):
        return response.task
    raise ValueError("StreamResponse has no payload field set")


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
    *,
    kind: ContentKind | None = None,
) -> None:
    """Send a working status update with optional emoji prefix.

    ``kind`` tags the outbound message under
    ``KOURAI_KIND_METADATA_KEY``. Hosts route by kind: ``KIND_STATUS``
    skips TTS and fires-and-forgets; ``KIND_DIALOGUE`` keeps the current
    speak-and-gate behavior. Leaving ``kind=None`` preserves the v0.x
    text-parsing path so unmigrated agents keep working.
    """
    msg = updater.new_agent_message(parts=[text_part(f"{emoji} {message}")])
    if kind is not None:
        set_content_kind(msg, kind)
    await updater.start_work(message=msg)


async def send_input_required(
    updater: TaskUpdater,
    task: Task,
    message: str,
    *,
    kind: ContentKind | None = None,
) -> None:
    """Request user input and mark the task as paused.

    ``kind`` defaults to ``None`` for backwards compatibility, but
    callers should pass ``KIND_DIALOGUE`` — input-required prompts are
    addressed to the player and TTS-eligible.
    """
    msg = updater.new_agent_message(parts=[text_part(message)])
    if kind is not None:
        set_content_kind(msg, kind)
    await updater.requires_input(message=msg)


async def send_completed(
    updater: TaskUpdater,
    task: Task,
    message: str,
    emoji: str = "✅",
    *,
    kind: ContentKind | None = None,
) -> None:
    """Mark the task as completed with a final status message."""
    msg = updater.new_agent_message(parts=[text_part(f"{emoji} {message}")])
    if kind is not None:
        set_content_kind(msg, kind)
    await updater.complete(message=msg)
