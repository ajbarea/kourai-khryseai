"""Filesystem MCP server — file read/write/list/search as MCP tools over stdio.

Resources expose files via file:// URIs for context injection.
Tools handle write operations (which are explicit actions, not just reads).
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("kourai-filesystem")

# Maximum file size to read in one call — prevents accidental giant reads.
_MAX_READ_BYTES = 512 * 1024  # 512 KB


def _safe_path(path: str) -> Path:
    """Resolve path and return a Path object."""
    return Path(path).resolve()


# ── Resources (read-only context injection via file:// URIs) ─────────


@mcp.resource("file://{path}")
async def read_file_resource(path: str) -> str:
    """Expose a file as an MCP resource for context injection.

    Args:
        path: Absolute or relative file path.
    """
    p = _safe_path(path)
    if not p.exists():
        return f"(file not found: {path})"
    if p.stat().st_size > _MAX_READ_BYTES:
        return f"(file too large to read as resource: {p.stat().st_size} bytes)"
    return p.read_text(encoding="utf-8", errors="replace")


# ── Tools (read actions) ─────────────────────────────────────────────


@mcp.tool()
async def read_file(path: str, encoding: str = "utf-8") -> str:
    """Read a file's contents.

    Args:
        path: File path to read.
        encoding: Text encoding (default utf-8).

    Returns:
        File contents as a string, or an error message if unreadable.
    """
    p = _safe_path(path)
    if not p.exists():
        return f"error: file not found: {path}"
    if not p.is_file():
        return f"error: not a file: {path}"
    size = p.stat().st_size
    if size > _MAX_READ_BYTES:
        return f"error: file too large ({size} bytes, max {_MAX_READ_BYTES})"
    return p.read_text(encoding=encoding, errors="replace")


@mcp.tool()
async def list_directory(path: str = ".", max_depth: int = 2) -> str:
    """List directory contents up to max_depth levels deep.

    Args:
        path: Directory to list (default current directory).
        max_depth: Maximum recursion depth (default 2, max 4).

    Returns:
        Indented tree of files and directories.
    """
    max_depth = min(max_depth, 4)
    root = _safe_path(path)
    if not root.exists():
        return f"error: path not found: {path}"
    if not root.is_dir():
        return f"error: not a directory: {path}"

    lines: list[str] = [str(root)]

    def _walk(directory: Path, depth: int, prefix: str) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(
                directory.iterdir(),
                key=lambda e: (e.is_file(), e.name.lower()),
            )
        except PermissionError:
            return
        for i, entry in enumerate(entries):
            if entry.name.startswith(".") or entry.name == "__pycache__":
                continue
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir() and depth < max_depth:
                extension = "    " if i == len(entries) - 1 else "│   "
                _walk(entry, depth + 1, prefix + extension)

    _walk(root, 1, "")
    return "\n".join(lines)


@mcp.tool()
async def search_files(
    root: str = ".",
    pattern: str = "*.py",
    max_results: int = 100,
) -> str:
    """Find files matching a glob pattern under root.

    Args:
        root: Directory to search from (default current directory).
        pattern: Glob pattern to match filenames (default *.py).
        max_results: Maximum number of results to return (default 100).

    Returns:
        Newline-separated list of matching file paths.
    """
    root_path = _safe_path(root)
    if not root_path.exists():
        return f"error: path not found: {root}"

    results: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Skip hidden dirs and caches
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
        for filename in filenames:
            if fnmatch.fnmatch(filename, pattern):
                full = Path(dirpath) / filename
                results.append(str(full.relative_to(root_path)))
                if len(results) >= max_results:
                    results.append(f"... (truncated at {max_results} results)")
                    return "\n".join(sorted(results))

    return "\n".join(sorted(results)) if results else "(no matches)"


# ── Tools (write actions) ────────────────────────────────────────────


@mcp.tool()
async def write_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """Write content to a file, creating parent directories as needed.

    Args:
        path: File path to write.
        content: Text content to write.
        encoding: Text encoding (default utf-8).

    Returns:
        Confirmation message with bytes written, or error message.
    """
    p = _safe_path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return f"ok: wrote {len(content.encode(encoding))} bytes to {p}"
    except Exception as exc:
        return f"error: {exc}"


@mcp.tool()
async def delete_file(path: str) -> str:
    """Delete a file (not directories).

    Args:
        path: File path to delete.

    Returns:
        Confirmation or error message.
    """
    p = _safe_path(path)
    if not p.exists():
        return f"error: not found: {path}"
    if not p.is_file():
        return f"error: not a file (will not delete directories): {path}"
    try:
        p.unlink()
        return f"ok: deleted {p}"
    except Exception as exc:
        return f"error: {exc}"
