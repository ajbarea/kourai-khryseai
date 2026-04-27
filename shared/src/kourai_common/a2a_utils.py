"""Shared A2A protocol utilities for Kourai Khryseai agents.

Centralizes common A2A message handling patterns used across multiple agents.

A2A v1.0 migration
    The v1.0 spec unifies TextPart/FilePart/DataPart into a single Part
    type with member-based discrimination (``"text" in part``, ``"url" in
    part``) and renames ``mimeType`` → ``mediaType``. Card payloads are
    also backward-compatible, so a single SDK upgrade won't break us.
    All Part inspection in this repo funnels through ``_is_file_part()``
    and ``_get_file_bytes()`` — those two helpers are the v1.0 migration
    surface. Pyproject pins permit ``a2a-sdk<2.0`` so ``uv lock`` can
    pull 1.0.x once the upstream stable drops (ETA May-June 2026 per the
    a2a-protocol.org announcement).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from a2a.types import FileWithBytes

if TYPE_CHECKING:
    from a2a.server.agent_execution import RequestContext


# ── A2A protocol version negotiation ──────────────────────────────────

# The version we declare on every outbound A2A request via the
# ``A2A-Version`` header. v1.0 of the spec made this header REQUIRED for
# clients (servers assume 0.3 if absent — see
# https://a2a-protocol.org/latest/specification/). We declare 0.3
# explicitly so that when M7 lands an a2a-sdk 1.0.x server, the
# negotiation is unambiguous: this client speaks 0.3 today. Bump this
# constant in lockstep with the SDK pin in pyproject when M7 ships.
A2A_PROTOCOL_VERSION = "0.3"


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


# ── Project root extraction ───────────────────────────────────────────


_PROJECT_ROOT_PATTERNS = (
    re.compile(r"^Project root:\s*(.+)$", re.MULTILINE),
    re.compile(r"\[project_root:\s*([^\]]+)\]", re.IGNORECASE),
    re.compile(r"\[Project Settings\]:\s*root=([^\s\]]+)", re.IGNORECASE),
)
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


def parse_project_root(text: str) -> Path:
    """Recover the player's project directory from any context-injection format.

    Specialist agents (Kallos, Dokimasia, Techne) call this to get the worktree
    path so subprocesses and file writes land in the forge session directory
    instead of the Kourai codebase's cwd.

    Accepts all historical/current injection shapes defensively:
      * ``Project root: /path`` — canonical form injected by Hephaestus into the
        forge transcript.
      * ``[project_root: /path]`` — bracket tag the CLI prepends on the outbound
        prompt before Hephaestus strips it.
      * ``[Project Settings]: root=/path`` — legacy transcript key.

    Paths under ``.kourai_khryseai`` are translated from the host user's home
    to this process's home so the same path works from the CLI (host) and
    from specialist containers (bind-mounted at ``/home/kourai``).

    Falls back to ``Path.cwd()`` when no tag is present (internal tasks) or the
    parsed path no longer exists on disk.
    """
    for pattern in _PROJECT_ROOT_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = Path(match.group(1).strip())
            candidate = _translate_to_container(raw)
            if candidate.is_dir():
                return candidate
    return Path.cwd()


# ── Part inspection helpers (v1.0 migration firewall) ────────────────


def _is_file_part(root: Any) -> bool:
    """Return True if the Part root contains embedded file bytes.

    Supports SDK 0.3.x (FilePart with ``root.file`` = FileWithBytes) today
    and the v1.0 unified-Part shape (flat ``bytes`` + ``mediaType`` keys)
    as a forward-compatibility stub — v1.0 is pinned-but-unused; live
    traffic still travels the 0.3.x path.
    """
    if hasattr(root, "file") and isinstance(root.file, FileWithBytes):
        return True
    # v1.0 unified Part forward-compat — activated when a2a-sdk ≥ 1.0 lands.
    return hasattr(root, "bytes") and hasattr(root, "media_type")


def _get_file_bytes(root: Any) -> tuple[str, str]:
    """Extract (base64_bytes, mime_type) from a file Part root.

    Returns ``(bytes_str, mime_type)`` for both SDK 0.3.x (``root.file.bytes``
    + ``mime_type``) and the v1.0 unified Part (flat ``bytes`` +
    ``media_type``). Mime defaults to ``image/png`` if unset.
    """
    if hasattr(root, "file") and isinstance(root.file, FileWithBytes):
        return root.file.bytes, root.file.mime_type or "image/png"
    # v1.0 unified Part forward-compat.
    return root.bytes, getattr(root, "media_type", None) or "image/png"


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
        root = part.root
        if _is_file_part(root):
            b64, mime = _get_file_bytes(root)
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
    attachments: list[tuple[str, str]] = []
    if not context.message:
        return attachments

    for part in context.message.parts:
        root = part.root
        if _is_file_part(root):
            attachments.append(_get_file_bytes(root))
    return attachments
