"""Shared A2A protocol utilities for Kourai Khryseai agents.

Centralizes common A2A message handling patterns used across multiple agents.

A2A v1.0 migration — status as of 2026-04-29
    a2a-sdk 1.0.0 stable shipped 2026-04-20; current is 1.0.2 (2026-04-24).
    The migration is *bigger* than this firewall anticipated:

    - Predicted: v1.0 would unify ``TextPart`` / ``FilePart`` / ``DataPart``
      into a single Part type with member discrimination (``hasattr(root,
      "bytes") and hasattr(root, "media_type")``).
    - Reality: v1.0 *removed* ``TextPart`` / ``FilePart`` / ``DataPart`` /
      ``FileWithBytes`` / ``FileWithUri`` entirely. Construction is now
      ``Part(text="...")`` or ``Part(raw=bytes, media_type="...",
      filename="...")`` — flat fields on Part itself, not member discrim
      on a tagged-union root. The ``hasattr(root, "bytes")`` branch below
      still works *by accident* because protobuf message attribute access
      is permissive; the ``hasattr(root, "media_type")`` check matches the
      actual v1.0 field name. So the firewall happens to fall through
      correctly, but the prediction was wrong and a future reader should
      rewrite the helpers against the actual v1.0 shape during M7 rather
      than treating this code as load-bearing.

    The bigger ticket items not addressed by this file:

    - ``A2AStarletteApplication`` is removed; every agent's ``__main__.py``
      needs rewriting against ``create_agent_card_routes`` +
      ``create_jsonrpc_routes`` from ``a2a.server.routes``.
    - All enums switched ``snake_case`` → ``SCREAMING_SNAKE_CASE``
      (``TaskState.working`` → ``TASK_STATE_WORKING``,
      ``Role.user`` → ``ROLE_USER``).
    - ``ClientFactory.create_client()`` is sync-deprecated; new path is
      ``await create_client(url_or_card)`` from ``a2a.client``.
    - ``AgentCard`` overhaul: top-level ``url`` removed, ``examples`` /
      ``input_modes`` / ``output_modes`` moved into ``AgentSkill`` /
      ``default_input_modes`` / ``default_output_modes``.
    - ``DefaultRequestHandler`` requires ``agent_card=`` now.
    - Streaming: ``AsyncIterator[ClientEvent | Message]`` →
      ``AsyncIterator[StreamResponse]`` with ``HasField('artifact_update'
      | 'status_update' | 'task' | 'message')`` checks.
    - Server-side ``enable_v0_3_compat=True`` flag exists on
      ``create_jsonrpc_routes`` / ``create_rest_routes`` for legacy
      clients; not reachable today since the application-setup refactor
      is itself a precondition.

    See ROADMAP §M7 for the milestone scope and the upstream migration
    guide at ``a2aproject/a2a-python/blob/main/docs/migrations/v1_0/``.

A2A protocol-version negotiation
    Every outbound request carries an ``A2A-Version`` header per the
    v1.0 spec. We declare 0.3 explicitly today so a 1.0.x server can
    negotiate down rather than silently downgrading. ``A2A_PROTOCOL_VERSION``
    is the single bump-site when M7 ships.
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

# Single bump-site for M7. Today's clients declare 0.3 explicitly so a
# 1.0.x server can negotiate down. Flipping this to ``"1.0"`` is one of
# the last steps of the M7 cutover, paired with the pin bump in pyproject
# and the application-setup refactor noted in this module's docstring.
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


# ── Part inspection helpers (live 0.3.x; M7 will rewrite) ────────────


def _is_file_part(root: Any) -> bool:
    """Return True if the Part root contains embedded file bytes.

    Today's path: SDK 0.3.x ``FilePart`` with ``root.file`` = ``FileWithBytes``.

    The second branch was a forward-compat stub that predicted the v1.0
    Part shape would be a tagged union with ``bytes`` / ``media_type``
    members; the real 1.0 shape is flat fields directly on ``Part``
    (``Part(raw=bytes, media_type="...")``), no nested root. The check
    happens to match anyway because protobuf attribute access is
    permissive, but M7 should rewrite both helpers against the actual
    v1.0 surface rather than relying on this accidental match.
    """
    if hasattr(root, "file") and isinstance(root.file, FileWithBytes):
        return True
    return hasattr(root, "bytes") and hasattr(root, "media_type")


def _get_file_bytes(root: Any) -> tuple[str, str]:
    """Extract (base64_bytes, mime_type) from a file Part root.

    Same caveat as ``_is_file_part`` — the v1.0 branch happens to work
    against protobuf attribute access but assumes a tagged-union shape
    that didn't ship. Rewrite both during M7.
    """
    if hasattr(root, "file") and isinstance(root.file, FileWithBytes):
        return root.file.bytes, root.file.mime_type or "image/png"
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
