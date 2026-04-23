"""Tests for the kourai-shell MCP server.

The shell server exposes ``run_command`` and ``which`` for agents. These
tests focus on the public contract: the tool descriptions that land in
``tools/list``, and the allowlist behavior that protects the sandbox.
"""

from __future__ import annotations

import pytest
from kourai_mcp_shell.server import _check_allowed, mcp


@pytest.mark.asyncio
async def test_run_command_advertises_large_result_size() -> None:
    """Claude Code reads ``_meta["anthropic/maxResultSizeChars"]`` from a
    tool's description to decide how much of its output to keep. Without
    this annotation, ``pytest`` / ``ruff`` output hits the 25K default and
    gets truncated mid-traceback.
    """
    tools = await mcp.list_tools()
    run_command = next((t for t in tools if t.name == "run_command"), None)
    assert run_command is not None
    assert run_command.meta is not None
    assert run_command.meta.get("anthropic/maxResultSizeChars") == 500_000


def test_check_allowed_rejects_unknown_executable() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        _check_allowed(["curl", "https://example.com"])


def test_check_allowed_accepts_ruff() -> None:
    _check_allowed(["ruff", "check", "."])


def test_check_allowed_accepts_full_path() -> None:
    """Full-path invocations (``/usr/bin/git``) pass once the basename is allowlisted."""
    _check_allowed(["/usr/bin/git", "status"])
