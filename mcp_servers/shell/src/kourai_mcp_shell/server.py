"""Shell MCP server — exposes run_command as an MCP tool over stdio.

Security: only commands whose executable name matches _ALLOWED_COMMANDS are
permitted. Agents should connect via StdioServerParameters, which restricts
access to the launching process only (no network exposure).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("kourai-shell")

# Allowlist prevents prompt-injection attacks from convincing an agent to
# run arbitrary shell commands. Only the tools the agents actually need.
_ALLOWED_COMMANDS: frozenset[str] = frozenset(
    {
        "ruff",
        "ty",
        "pytest",
        "git",
        "python",
        "python3",
        "uv",
        "node",
        "npx",
        "chub",  # Context Hub CLI for documentation lookup
    }
)


def _resolve_executable(cmd: str) -> str:
    """Return the bare executable name for allowlist checking."""
    # Handle full paths like /usr/bin/git or .venv/bin/python
    return Path(cmd).name.split(".")[0]  # strip .exe on Windows


def _check_allowed(cmd: list[str]) -> None:
    """Raise ValueError if cmd[0] is not in the allowlist."""
    if not cmd:
        raise ValueError("Empty command")
    name = _resolve_executable(cmd[0])
    if name not in _ALLOWED_COMMANDS:
        raise ValueError(
            f"Command {cmd[0]!r} is not allowed. Permitted executables: {sorted(_ALLOWED_COMMANDS)}"
        )


# anthropic/maxResultSizeChars tells Claude Code-style clients not to truncate
# tool output below 500K chars — `pytest` / `ruff` tracebacks routinely exceed
# the default 25K limit, and truncated output loses the actual failure.
@mcp.tool(meta={"anthropic/maxResultSizeChars": 500_000})
async def run_command(
    cmd: list[str],
    cwd: str | None = None,
    timeout_seconds: int = 120,
) -> str:
    """Run an allowlisted shell command and return combined stdout + stderr.

    Args:
        cmd: Command and arguments (e.g. ["python", "-m", "pytest", "tests/"]).
        cwd: Working directory. Defaults to the server's process cwd.
        timeout_seconds: Maximum seconds to wait before killing the process (default 120).

    Returns:
        Combined stdout and stderr, prefixed with the exit code.

    Raises:
        ValueError: If cmd[0] is not in the allowlist.
        TimeoutError: If the command exceeds the timeout.
    """
    _check_allowed(cmd)

    effective_cwd = cwd or str(Path.cwd())
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=effective_cwd,
        )
        try:
            async with asyncio.timeout(timeout_seconds):
                stdout, stderr = await proc.communicate()
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            raise TimeoutError(
                f"Command timed out after {timeout_seconds}s: {' '.join(cmd)}"
            ) from None

        rc = proc.returncode or 0
        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")
        parts = [f"exit: {rc}"]
        if out.strip():
            parts.append(out.rstrip())
        if err.strip():
            parts.append(f"stderr:\n{err.rstrip()}")
        return "\n".join(parts)

    except TimeoutError:
        raise
    except Exception as exc:
        return f"exit: 1\nerror: {exc}"


@mcp.tool()
async def which(name: str) -> str:
    """Resolve the full path of an allowlisted executable.

    Useful for agents that need the absolute path (e.g. sys.executable equivalent).

    Args:
        name: Executable name to look up (must be in allowlist).

    Returns:
        Full path string, or an error message if not found.
    """
    _check_allowed([name])
    if sys.platform == "win32":
        cmd = ["where", name]
    else:
        cmd = ["which", name]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    result = stdout.decode("utf-8", errors="replace").strip()
    return result or f"not found: {name}"
