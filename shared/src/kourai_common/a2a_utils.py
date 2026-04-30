"""Shared A2A protocol utilities for Kourai Khryseai agents.

Two surfaces:

* ``make_a2a_http_client`` — outbound httpx client with the
  ``A2A-Version`` header pre-set. Single bump-site for the protocol
  version when M7 ships.
* ``parse_project_root`` — recover the player's project worktree
  from any historical text-tag injection shape so specialist
  containers run subprocesses in the right repo.
* ``extract_image_parts`` / ``extract_file_attachments`` — read the
  inbound A2A message for FileWithBytes attachments and re-shape them
  for LiteLLM (image_url blocks) or kourai-internal use (raw b64 +
  mime tuples). Wire-shape inspection lives in
  ``kourai_common.messaging.is_file_part`` / ``get_file_bytes``.

See ROADMAP §M7 for the in-flight a2a-sdk 1.0 migration plan. This
module's piece — Part inspection — was the dual-shape firewall before
2026-04-29; Phase 2 moved inspection into ``messaging`` so this file
is now firewall-free.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from kourai_common.messaging import get_file_bytes, is_file_part

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
