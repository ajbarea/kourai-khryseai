"""Shared A2A protocol utilities for Kourai Khryseai agents.

Surfaces:

* ``make_a2a_http_client`` — outbound httpx client with the
  ``A2A-Version`` header pre-set. Single bump-site for the protocol
  version.
* ``get_message_metadata`` / ``project_root_from_context`` — read the
  inbound message's structured ``Message.metadata`` (the v1.0 home
  for forge context like ``project_root``, ``project_id``, ``yolo``).
  Replaces the text-tag regex extraction Phase 5 retired.
* ``extract_image_parts`` / ``extract_file_attachments`` — read the
  inbound A2A message for raw-bytes file Parts and re-shape them for
  LiteLLM (image_url blocks) or kourai-internal use (b64 + mime
  tuples). Wire-shape inspection lives in
  ``kourai_common.messaging.is_file_part`` / ``get_file_bytes``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from kourai_common.messaging import get_file_bytes, is_file_part

if TYPE_CHECKING:
    from a2a.server.agent_execution import RequestContext


# ── A2A protocol version negotiation ──────────────────────────────────

# v1.0 SDK landed across the stack in M7 Phase 3; clients declare 1.0
# explicitly so the server stops falling through the compat shim. The
# server still honours v0.3 clients via ``enable_v0_3_compat=True`` —
# Phase 6 retires that fallback.
A2A_PROTOCOL_VERSION = "1.0"


def make_a2a_http_client(
    *,
    timeout: float | httpx.Timeout | None = None,
    extra_headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    """Construct an ``httpx.AsyncClient`` carrying the ``A2A-Version`` header.

    Every outbound A2A request now MUST carry this header per the v1.0
    spec — without it, a v1.0 server silently downgrades to 0.3
    semantics. Centralising the construction means we have one place
    to bump the version when M7 (a2a-sdk 1.0 migration) is ready, and
    every client (CLI, GUI, VN bridge, Hephaestus → specialist) gets
    the header for free.

    ``timeout`` is forwarded as-is to ``httpx.AsyncClient`` so callers
    keep their existing timeout policy. ``extra_headers`` merges into
    the version header for callers that need additional defaults
    (rare — pre-shared auth, tracing).
    """
    headers: dict[str, str] = {"A2A-Version": A2A_PROTOCOL_VERSION}
    if extra_headers:
        headers.update(extra_headers)
    if timeout is None:
        return httpx.AsyncClient(headers=headers)
    return httpx.AsyncClient(timeout=timeout, headers=headers)


# ── Message.metadata accessors ────────────────────────────────────────

# The CLI runs as the host user (/home/<host_user>/.kourai_khryseai/...)
# while specialists run inside containers that bind-mount the same dir at
# /home/kourai/.kourai_khryseai. _translate_to_container rewrites any host
# path pointing into .kourai_khryseai to the container-local form.
_PROJECTS_MARKER = ".kourai_khryseai"


def _translate_to_container(path: Path) -> Path:
    """Remap host-side .kourai_khryseai paths into this process's $HOME mirror.

    On the host, the CLI emits paths like /home/ajbar/.kourai_khryseai/projects/...
    Inside a specialist container the same tree is mounted at
    /home/kourai/.kourai_khryseai, so the host prefix must be rewritten before
    the path can be opened.
    """
    parts = path.parts
    for i, segment in enumerate(parts):
        if segment == _PROJECTS_MARKER:
            local = Path.home() / _PROJECTS_MARKER
            return local.joinpath(*parts[i + 1 :]) if i + 1 < len(parts) else local
    return path


def get_message_metadata(context: RequestContext | None) -> dict[str, Any]:
    """Return the inbound message's metadata as a plain Python dict.

    Reads ``context.message.metadata`` and unwraps it. Real protobuf
    ``Struct`` values flow through ``MessageToDict`` so callers see
    plain Python (``str``, ``int``, ``float``, ``bool``, ``list``,
    ``dict``); plain-dict fixtures (unit-test mocks) come back as-is.
    Returns ``{}`` when the context has no message or the message has
    no metadata.
    """
    if context is None:
        return {}
    message = getattr(context, "message", None)
    if message is None:
        return {}
    metadata = getattr(message, "metadata", None)
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return dict(metadata)
    if hasattr(metadata, "DESCRIPTOR"):
        try:
            from google.protobuf.json_format import MessageToDict

            return MessageToDict(metadata)
        except (TypeError, ValueError, ImportError):
            pass
    try:
        return dict(metadata)
    except (TypeError, ValueError):
        return {}


def project_root_from_context(context: RequestContext | None) -> Path:
    """Recover the player's project worktree from ``Message.metadata``.

    Specialist agents (Kallos, Dokimasia, Techne, Metis) call this to
    resolve the forge worktree so subprocesses and file writes land in
    the right directory instead of the container's ``/app`` cwd. The
    path is translated from host-user home to the container's home so
    the same value works on both sides of the bind mount.

    Falls back to ``Path.cwd()`` when no ``project_root`` metadata key
    is present (internal tasks, smoke tests) or the parsed path no
    longer exists on disk.
    """
    raw = get_message_metadata(context).get("project_root")
    if isinstance(raw, str) and raw.strip():
        candidate = _translate_to_container(Path(raw.strip()))
        if candidate.is_dir():
            return candidate
    return Path.cwd()


# ── Public API ───────────────────────────────────────────────────────


def extract_image_parts(context: RequestContext) -> list[dict]:
    """Build LiteLLM image_url blocks from any FilePart in the incoming message.

    Args:
        context: A2A request context containing the incoming message.

    Returns:
        List of LiteLLM-compatible image_url dictionaries for multimodal chat.
        Empty list if no files present.

    Example:
        >>> image_parts = extract_image_parts(context)
        >>> messages = [
        ...     {"role": "user", "content": [{"type": "text", "text": "..."}, *image_parts]}
        ... ]
    """
    image_parts: list[dict] = []
    if not context.message:
        return image_parts

    for part in context.message.parts:
        if is_file_part(part):
            b64, mime = get_file_bytes(part)
            image_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                }
            )
    return image_parts


def extract_file_attachments(context: RequestContext) -> list[tuple[str, str]]:
    """Extract raw file data from A2A message as (bytes, mime_type) tuples.

    Args:
        context: A2A request context containing the incoming message.

    Returns:
        List of (base64_bytes, mime_type) tuples. Empty list if no files present.

    Example:
        >>> attachments = extract_file_attachments(context)
        >>> for bytes_data, mime_type in attachments:
        ...     process_file(bytes_data, mime_type)
    """
    if not context.message:
        return []
    return [get_file_bytes(part) for part in context.message.parts if is_file_part(part)]
