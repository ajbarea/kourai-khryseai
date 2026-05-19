"""Structured dev-session logger.

A single session writes to ``logs/dev-runner-latest.log`` (truncated on open
so the newest run is at a stable path) plus a timestamped archive. Subprocess
output is streamed live to the terminal *and* teed to the log with ISO
timestamps and per-step context tags. Every session ends with a SUMMARY block
listing per-step rc + elapsed.

When ``KOURAI_DEV_SESSION=1`` is set in the environment, ``DevLog.open()``
becomes a no-op so a child process invoked from another DevLog session does
not truncate its parent's log file. The child still streams to the console
and the parent captures everything via its own ``run_step``.

Usage:
    from kourai_common.dev_log import LOG, run_step

    LOG.open("lint")
    LOG.session_header("lint", sys.argv[1:])
    try:
        run_step(["ruff", "format", "."], label="format")
        run_step(["ruff", "check", "."], label="check", check=False)
    finally:
        LOG.session_footer(overall_rc=0)
"""

from __future__ import annotations

import atexit
import contextlib
import datetime as _dt
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from typing import IO, TYPE_CHECKING, TypedDict

from kourai_common.paths import PROJECT_ROOT as ROOT, logs_dir as _logs_dir

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


class StepRecord(TypedDict):
    name: str
    rc: int
    elapsed: float


LOGS_DIR = _logs_dir()
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
SESSION_ENV = "KOURAI_DEV_SESSION"

_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
C_BOLD = "\033[1m" if _USE_COLOR else ""
C_DIM = "\033[2m" if _USE_COLOR else ""
C_RED = "\033[31m" if _USE_COLOR else ""
C_GREEN = "\033[32m" if _USE_COLOR else ""
C_YELLOW = "\033[33m" if _USE_COLOR else ""
C_CYAN = "\033[36m" if _USE_COLOR else ""
C_RESET = "\033[0m" if _USE_COLOR else ""


class StepFailedError(RuntimeError):
    """Raised when a step exits non-zero and ``check=True`` was requested."""

    def __init__(self, cmd: Sequence[str], returncode: int) -> None:
        super().__init__(f"{' '.join(cmd)} exited with {returncode}")
        self.cmd = list(cmd)
        self.returncode = returncode


class DevLog:
    # The handle intentionally outlives __init__ (one file per session),
    # so a context-manager pattern doesn't fit — atexit closes it instead.
    def __init__(self) -> None:
        self.file: IO[str] | None = None
        self.latest_path: Path | None = None
        self.archive_path: Path | None = None
        self.started = time.monotonic()
        self.step_stack: list[str] = []
        self.steps: list[StepRecord] = []
        self.nested = False

    def open(self, command: str) -> None:
        # If a parent dev session already owns the log file, stay quiet:
        # the parent's run_step will capture our subprocess output via PIPE.
        if os.environ.get(SESSION_ENV) == "1":
            self.nested = True
            return
        LOGS_DIR.mkdir(exist_ok=True)
        ts = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        self.latest_path = LOGS_DIR / "dev-runner-latest.log"
        self.archive_path = LOGS_DIR / f"dev-{ts}-{command}.log"
        self.file = self.latest_path.open("w", encoding="utf-8", buffering=1)
        atexit.register(self.close)

    def close(self) -> None:
        if self.file and not self.file.closed:
            try:
                self.file.flush()
                if self.latest_path and self.archive_path:
                    with contextlib.suppress(OSError):
                        shutil.copy2(self.latest_path, self.archive_path)
            finally:
                self.file.close()

    def _write(self, line: str) -> None:
        if self.file and not self.file.closed:
            self.file.write(ANSI_RE.sub("", line))
            if not line.endswith("\n"):
                self.file.write("\n")

    def event(self, level: str, msg: str) -> None:
        if self.nested:
            return
        ts = _dt.datetime.now().isoformat(timespec="milliseconds")
        ctx = "/".join(self.step_stack) or "-"
        self._write(f"[{ts}] [{level:<5}] [{ctx}] {msg}")

    def raw(self, text: str) -> None:
        if self.nested:
            return
        ts = _dt.datetime.now().isoformat(timespec="milliseconds")
        ctx = "/".join(self.step_stack) or "-"
        for line in text.splitlines() or [""]:
            self._write(f"[{ts}] [OUT  ] [{ctx}] {line}")

    def push_step(self, name: str) -> None:
        self.step_stack.append(name)
        self.event("STEP", f"enter {name}")

    def pop_step(self, name: str, *, rc: int, elapsed: float) -> None:
        self.event("STEP", f"exit  {name} rc={rc} elapsed={elapsed:.2f}s")
        self.steps.append({"name": name, "rc": rc, "elapsed": elapsed})
        if self.step_stack and self.step_stack[-1] == name:
            self.step_stack.pop()

    def session_header(self, command: str, argv: Sequence[str]) -> None:
        if self.nested:
            return

        def capture(cmd: Sequence[str]) -> str:
            try:
                out = subprocess.run(  # noqa: S603
                    list(cmd),
                    cwd=str(ROOT),
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return (
                    (out.stdout or out.stderr).strip().splitlines()[0]
                    if (out.stdout or out.stderr)
                    else ""
                )
            except (OSError, subprocess.TimeoutExpired):
                return ""

        git_sha = capture(["git", "rev-parse", "--short", "HEAD"]) or "unknown"
        git_branch = capture(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
        git_dirty = capture(["git", "status", "--porcelain"])
        uv_ver = capture(["uv", "--version"])
        docker_ver = capture(["docker", "--version"])

        header = [
            "=" * 78,
            "kourai-khryseai dev runner — session log",
            "=" * 78,
            f"started    : {_dt.datetime.now().isoformat(timespec='seconds')}",
            f"command    : {command}",
            f"argv       : {' '.join(argv)}",
            f"cwd        : {ROOT}",
            f"platform   : {platform.platform()}",
            f"python     : {sys.version.split()[0]} ({sys.executable})",
            f"uv         : {uv_ver or 'not found'}",
            f"docker     : {docker_ver or 'not found'}",
            f"git branch : {git_branch}",
            f"git sha    : {git_sha}",
            f"git dirty  : {'yes' if git_dirty else 'no'}",
            "=" * 78,
            "",
            "# Log format: [ISO-timestamp] [LEVEL] [step/path] message",
            "# LEVELS: INFO, STEP, WARN, ERROR, OUT (subprocess stdout+stderr merged)",
            "# See the SUMMARY block at the bottom for per-step exit codes.",
            "",
        ]
        for line in header:
            self._write(line)

    def session_footer(self, overall_rc: int) -> None:
        if self.nested:
            return
        elapsed = time.monotonic() - self.started
        failed = [s for s in self.steps if s["rc"] != 0]
        lines = [
            "",
            "=" * 78,
            "SUMMARY",
            "=" * 78,
            f"total elapsed : {elapsed:.2f}s",
            f"steps run     : {len(self.steps)}",
            f"steps failed  : {len(failed)}",
            f"overall rc    : {overall_rc}",
            "",
            "per-step:",
        ]
        for s in self.steps:
            mark = "PASS" if s["rc"] == 0 else "FAIL"
            lines.append(f"  {mark}  rc={s['rc']:<3} {s['elapsed']:>6.2f}s  {s['name']}")
        if failed:
            lines += [
                "",
                "DEBUG HINTS",
                "-----------",
                "Grep this log for the failing step name to find its subprocess output.",
                "Each [OUT  ] line is merged stdout+stderr, tagged with its step.",
                "rc=127 means the binary was not on PATH.",
            ]
        lines += ["=" * 78, ""]
        for line in lines:
            self._write(line)


LOG = DevLog()


def print_header(title: str) -> None:
    print(f"\n{C_BOLD}{C_CYAN}== {title} =={C_RESET}", flush=True)
    LOG.event("INFO", f"=== {title} ===")


def _print_step(cmd: Sequence[str], *, label: str | None = None) -> None:
    prefix = f"{C_DIM}$ {C_RESET}"
    printed = " ".join(cmd)
    tag = f" {C_DIM}({label}){C_RESET}" if label else ""
    print(f"{prefix}{printed}{tag}", flush=True)


def run_step(
    cmd: Sequence[str],
    *,
    check: bool = True,
    label: str | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> int:
    """Stream a command's merged stdout+stderr to console + log file.

    Missing-binary failures are surfaced as rc=127.
    """
    step_label = label or " ".join(cmd)
    _print_step(cmd, label=label)
    LOG.push_step(step_label)
    LOG.event("INFO", f"cmd: {' '.join(cmd)}")
    started = time.monotonic()
    rc: int
    try:
        proc = subprocess.Popen(  # noqa: S603
            list(cmd),
            cwd=str(cwd or ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            env=env,
        )
    except FileNotFoundError as exc:
        LOG.event("ERROR", f"binary not found: {cmd[0]}")
        LOG.pop_step(step_label, rc=127, elapsed=time.monotonic() - started)
        if check:
            raise StepFailedError(cmd, 127) from exc
        return 127

    try:
        if proc.stdout is not None:
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                LOG.raw(line.rstrip("\n"))
    finally:
        rc = proc.wait()

    elapsed = time.monotonic() - started
    LOG.pop_step(step_label, rc=rc, elapsed=elapsed)
    if rc != 0:
        LOG.event("ERROR" if check else "WARN", f"exit {rc} after {elapsed:.2f}s")
    if check and rc != 0:
        raise StepFailedError(cmd, rc)
    return rc
