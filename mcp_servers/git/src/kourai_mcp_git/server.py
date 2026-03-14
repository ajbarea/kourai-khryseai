"""Git MCP server — read-only git operations exposed as MCP tools over stdio.

All tools are read-only (status, diff, log, blame, show). Write operations
(commit, push, branch creation) are intentionally excluded — those stay under
direct agent control as explicit, audited actions.
"""

from __future__ import annotations

import asyncio
import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("kourai-git")


async def _git(args: list[str], cwd: str | None = None) -> tuple[int, str]:
    """Run a git subcommand and return (returncode, combined output)."""
    effective_cwd = cwd or os.getcwd()
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=effective_cwd,
    )
    stdout, stderr = await proc.communicate()
    out = stdout.decode("utf-8", errors="replace")
    err = stderr.decode("utf-8", errors="replace")
    combined = (out + err).strip()
    return proc.returncode or 0, combined


@mcp.tool()
async def git_status(cwd: str | None = None) -> str:
    """Return working tree status (equivalent to git status --short).

    Args:
        cwd: Repository root. Defaults to process cwd.
    """
    _, output = await _git(["status", "--short"], cwd=cwd)
    return output or "(clean)"


@mcp.tool()
async def git_diff(
    cwd: str | None = None,
    staged: bool = False,
    paths: list[str] | None = None,
) -> str:
    """Return a unified diff of unstaged (or staged) changes.

    Args:
        cwd: Repository root.
        staged: If True, show staged (--cached) changes instead of unstaged.
        paths: Optional list of paths to scope the diff.
    """
    args = ["diff"]
    if staged:
        args.append("--cached")
    if paths:
        args.extend(["--", *paths])
    _, output = await _git(args, cwd=cwd)
    return output or "(no changes)"


@mcp.tool()
async def git_log(
    cwd: str | None = None,
    n: int = 10,
    oneline: bool = True,
) -> str:
    """Return recent commit history.

    Args:
        cwd: Repository root.
        n: Number of commits to show (default 10).
        oneline: If True, compact one-line format (default True).
    """
    args = ["log", f"-{n}"]
    if oneline:
        args.append("--oneline")
    _, output = await _git(args, cwd=cwd)
    return output or "(no commits)"


@mcp.tool()
async def git_blame(path: str, cwd: str | None = None) -> str:
    """Return git blame output for a file.

    Args:
        path: File path relative to cwd.
        cwd: Repository root.
    """
    _, output = await _git(["blame", "--porcelain", path], cwd=cwd)
    return output


@mcp.tool()
async def git_show(ref: str, cwd: str | None = None) -> str:
    """Show content of a commit, tag, or blob.

    Args:
        ref: Git ref (commit hash, tag, HEAD~1, etc.).
        cwd: Repository root.
    """
    _, output = await _git(["show", ref], cwd=cwd)
    return output


@mcp.tool()
async def git_branch(cwd: str | None = None) -> str:
    """List all local branches, marking the current one with *.

    Args:
        cwd: Repository root.
    """
    _, output = await _git(["branch", "-v"], cwd=cwd)
    return output or "(no branches)"
