"""kourai-mcp-forge — FastMCP server exposing the M1 forge file ops.

Tools mirror the existing ``kourai_common.forge_tools`` registry exactly
(``read_file``, ``write_file``, ``edit_file``, ``delete_file``); each
delegates to the same async handler the in-process tool-use loop uses,
so the path-safety story (``validate_file_path`` + ``PathViolation``) is
single-sourced. The MCP layer's job is purely protocol wiring + roots
resolution.

Roots scoping: every file-touching tool calls
``ctx.session.list_roots()`` to discover the player's project root on
demand. The kourai client declares ``roots`` capability via
``build_client_session`` (M2 Change 1) and populates
``kourai_project_root_var`` from each specialist executor (Change 1
follow-on), so the round-trip lands the same project root that the
in-process forge tools see today.

Multiple roots = first wins with a log warning. Empty roots = clear
error pointing the client at ``kourai_project_root_var`` so a
contributor can trace why nothing's scoped.

Tool annotations stay conservative per the 2025-11-25 spec note: tool
annotations are explicitly untrusted unless the server is trusted, so
the host's permission gate remains source of truth.
"""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import unquote, urlparse

from mcp.server.fastmcp import Context, FastMCP

from kourai_common import forge_tools

log = logging.getLogger(__name__)

mcp = FastMCP("kourai-forge")


_NO_ROOTS_ERROR = (
    "ERROR: no project root scoped — host returned empty roots/list. "
    "Check that `kourai_project_root_var` is set on the calling session "
    "(see M2 Change 1 follow-on; specialist executors set it from "
    "[project_root: ...] tags)."
)


async def _resolve_project_root(ctx: Context) -> Path | str:
    """Pull the player's project root from the host's declared roots.

    Returns the resolved ``Path`` on success, or an ``ERROR: ...`` string
    that the calling tool returns verbatim — mirroring
    ``forge_tools``' string-error convention rather than raising.
    """
    try:
        result = await ctx.session.list_roots()
    except Exception as exc:
        return f"ERROR: server requires `roots` capability — host did not answer roots/list: {exc}"
    if not result.roots:
        return _NO_ROOTS_ERROR
    if len(result.roots) > 1:
        log.warning(
            "Host declared %d roots; using the first (%s)",
            len(result.roots),
            result.roots[0].uri,
        )
    parsed = urlparse(str(result.roots[0].uri))
    return Path(unquote(parsed.path))


@mcp.tool()
async def read_file(path: str, ctx: Context) -> str:
    """Read a regular file's contents (line-numbered) from the project root.

    Path is project-relative — anything escaping the host's declared root
    is rejected by the existing ``validate_file_path`` guard.
    """
    project_root = await _resolve_project_root(ctx)
    if isinstance(project_root, str):
        return project_root
    return await forge_tools.read_file(path, project_root=project_root)


@mcp.tool()
async def write_file(path: str, content: str, ctx: Context) -> str:
    """Create or overwrite a file at the project-relative path."""
    project_root = await _resolve_project_root(ctx)
    if isinstance(project_root, str):
        return project_root
    return await forge_tools.write_file(path, content, project_root=project_root)


@mcp.tool()
async def edit_file(
    path: str,
    old_string: str,
    new_string: str,
    ctx: Context,
) -> str:
    """Replace exactly one occurrence of ``old_string`` with ``new_string``.

    Fails if ``old_string`` is missing or appears more than once. Extend
    the match with surrounding context to make it unique.
    """
    project_root = await _resolve_project_root(ctx)
    if isinstance(project_root, str):
        return project_root
    return await forge_tools.edit_file(path, old_string, new_string, project_root=project_root)


@mcp.tool()
async def delete_file(path: str, ctx: Context) -> str:
    """Remove a file from the project. No-op if it does not exist."""
    project_root = await _resolve_project_root(ctx)
    if isinstance(project_root, str):
        return project_root
    return await forge_tools.delete_file(path, project_root=project_root)
