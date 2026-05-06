"""Cross-platform developer entrypoints for Kourai Khryseai.

The canonical local workflow is:

    uv run kourai-dev <command> [-- <args...>]

The Makefile remains available as a thin compatibility wrapper, but this
module is the single source of truth for supported developer commands.

Output captured by ``DevLog`` (see ``kourai_common.dev_log``) lands in
``logs/dev-latest.log`` plus a timestamped archive. Tasks marked ``tee=True``
stream through ``run_step``; ``tee=False`` tasks (interactive GUIs, docker
attaches, the HF setup prompt) pass through directly so stdin/TTY behavior is
preserved.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from kourai_common.dev_log import LOG, SESSION_ENV, run_step
from kourai_common.paths import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_ENV = {
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
    "LC_ALL": "en_US.UTF-8",
    "LANG": "en_US.UTF-8",
}

# Commands where the user's intent is "wipe logs/". Purged by the parent session
# before LOG.open() so the child clean_build.py's _filter_logs guard (which keeps
# it from deleting the parent's live log file) doesn't make logs/ un-cleanable.
LOG_PURGING_COMMANDS = frozenset({"clean", "clean-tests", "yolo"})

CommandFactory = Callable[[], list[str]]


@dataclass(frozen=True)
class Task:
    """Metadata describing a developer task."""

    description: str
    command_factory: CommandFactory
    timed: bool = True
    cwd: Path = PROJECT_ROOT
    # tee=True -> stream through DevLog.run_step (captured to log + console).
    # tee=False -> direct passthrough so stdin/TTY behavior is preserved
    # (GUIs, docker attaches, interactive prompts).
    tee: bool = True


def _default_project_renpy_exe() -> Path:
    return PROJECT_ROOT / "hosts" / "vn" / "renpy-8.5.2-sdk" / "renpy.exe"


def resolve_renpy_executable() -> str:
    """Resolve the Ren'Py launcher across Linux/WSL, macOS, and Windows.

    On Linux (including WSL) we prefer ``renpy.sh`` from the same SDK —
    the Ren'Py 8.x SDK ships ``lib/py3-linux-x86_64/renpy`` alongside the
    Windows binary, so there's no need to go through Windows interop. On
    macOS we prefer the equivalent ``renpy.sh``. Native launchers give us
    normal stdout/stderr capture and no path-translation shenanigans.
    """
    env_override = os.environ.get("KOURAI_RENPY_EXE")
    candidates: list[Path] = []
    if env_override:
        candidates.append(Path(env_override))

    # Native-for-this-platform launchers first. renpy.sh works on both
    # Linux and macOS; .exe is the Windows path.
    if sys.platform != "win32":
        candidates.extend(
            [
                PROJECT_ROOT / "hosts" / "vn" / "renpy-8.5.2-sdk" / "renpy.sh",
                Path("/mnt/c/Tools/renpy-8.5.2-sdk/renpy.sh"),
                Path.home() / "renpy-8.5.2-sdk" / "renpy.sh",
            ]
        )

    candidates.extend(
        [
            _default_project_renpy_exe(),
            Path("/mnt/c/Tools/renpy-8.5.2-sdk/renpy.exe"),
            Path("C:/Tools/renpy-8.5.2-sdk/renpy.exe"),
        ]
    )

    for exe in candidates:
        if exe.exists():
            return str(exe)

    return str(_default_project_renpy_exe())


def _adapt_path_for_renpy(renpy_exe: str, path: str) -> str:
    """Translate a Linux path to a Windows path when handing it to renpy.exe.

    When ``make vn`` runs from WSL the resolver finds a Windows-native
    ``renpy.exe`` (the SDK is only installed on the Windows side for most
    devs). WSL can invoke ``.exe`` binaries, but the argv we pass through is
    Linux-rooted (``/home/<user>/ajsoftworks/...``), which Windows Ren'Py
    can't open — it exits ~1s later with status 5 ("project not found").

    ``wslpath -w`` converts the Linux path to the equivalent Windows UNC
    path (``\\\\wsl.localhost\\Ubuntu\\home\\<user>\\...``), which Ren'Py
    can load. We only do this conversion when (a) we're on Linux and (b)
    the resolved Ren'Py executable ends in ``.exe`` — native Linux/macOS
    SDKs don't need any translation.
    """
    if sys.platform != "linux" or not renpy_exe.lower().endswith(".exe"):
        return path
    wslpath_exe = shutil.which("wslpath")
    if wslpath_exe is None:
        return path
    try:
        result = subprocess.run(
            [wslpath_exe, "-w", path],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or path
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return path


def _cli_command() -> list[str]:
    """Build the argv for ``make cli``, honoring ``KOURAI_TTS`` for unattended runs.

    Default behavior is unchanged: ``make cli`` enables voice. Setting
    ``KOURAI_TTS=off`` in the environment opts out — needed for the smoke
    driver, headless CI, or any WSL2 host without an audio device, where
    the saved ``CLISettings.voice_enabled`` may otherwise be ``True`` and
    PortAudio errors out trying to open the default output device.
    """
    cmd = [
        sys.executable,
        "-m",
        "hosts.cli",
        "--agent",
        "http://localhost:10000/",
    ]
    tts_pref = os.environ.get("KOURAI_TTS", "").strip().lower()
    if tts_pref in ("off", "0", "false", "no"):
        cmd.append("--no-voice")
    else:
        cmd.append("--voice")
    return cmd


def _build_vn_command() -> list[str]:
    """Build the argv for launching the Ren'Py VN, adapting paths for WSL."""
    exe = resolve_renpy_executable()
    project = str(PROJECT_ROOT / "hosts" / "vn" / "kourai_vn")
    return [exe, _adapt_path_for_renpy(exe, project)]


def configure_stdio() -> None:
    """Prefer UTF-8 console output across shells."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (LookupError, OSError, ValueError):
                continue


def build_env() -> dict[str, str]:
    """Build the environment for child processes."""
    env = os.environ.copy()
    for key, value in DEFAULT_ENV.items():
        env.setdefault(key, value)

    # Tell child scripts a parent dev session owns the log file so their
    # DevLog.open() becomes a no-op (no truncation, no duplicate header).
    env[SESSION_ENV] = "1"

    wsl = os.environ.get("WSL_DISTRO_NAME")
    if sys.platform == "win32":
        expected_env = ".venv-wsl" if wsl else ".venv-win"
    else:
        expected_env = ".venv"

    configured_env = env.get("UV_PROJECT_ENVIRONMENT")
    if not configured_env or (sys.platform == "win32" and configured_env == ".venv"):
        env["UV_PROJECT_ENVIRONMENT"] = expected_env

    return env


def strip_passthrough_marker(args: list[str]) -> list[str]:
    """Allow ``--`` before passthrough arguments."""
    if args[:1] == ["--"]:
        return args[1:]
    return args


def python_script(*parts: str) -> list[str]:
    """Build a command for a repository Python script."""
    return ["uv", "run", "--no-active", "python", str(PROJECT_ROOT.joinpath(*parts))]


TASK_GROUPS: tuple[tuple[str, tuple[tuple[str, Task], ...]], ...] = (
    (
        "Environment",
        (
            (
                "check-env",
                Task(
                    description="Verify uv, Python, and Docker are available",
                    command_factory=lambda: python_script("scripts", "check_env.py"),
                ),
            ),
        ),
    ),
    (
        "Setup & Maintenance",
        (
            (
                "setup",
                Task(
                    description="Install all Python dependencies + optional HF Storage Buckets",
                    command_factory=lambda: python_script("scripts", "setup.py"),
                    # HF bucket setup may prompt for input — keep stdin attached.
                    tee=False,
                ),
            ),
            (
                "setup-artifacts",
                Task(
                    description="Create HF Storage Bucket for agent artifacts",
                    command_factory=lambda: python_script("scripts", "setup_buckets.py"),
                    tee=False,
                ),
            ),
            (
                "upgrade",
                Task(
                    description="Update all dependencies to latest versions",
                    command_factory=lambda: python_script("scripts", "upgrade.py"),
                ),
            ),
            (
                "yolo",
                Task(
                    description="Nuke and rebuild: clean -> down -> setup -> upgrade -> clean",
                    command_factory=list,
                    tee=False,
                ),
            ),
        ),
    ),
    (
        "Development Workflows",
        (
            (
                "up",
                Task(
                    description="Start all agents + infrastructure (fast: reuses containers)",
                    command_factory=lambda: ["docker", "compose", "up", "-d", "--wait"],
                    tee=False,
                ),
            ),
            (
                "down",
                Task(
                    description="Stop all services and remove containers",
                    command_factory=lambda: ["docker", "compose", "down", "--remove-orphans"],
                    tee=False,
                ),
            ),
            (
                "restart",
                Task(
                    description="Restart all services (down + up)",
                    command_factory=list,
                    tee=False,
                ),
            ),
            (
                "rebuild",
                Task(
                    description="Full rebuild with Docker cache clear",
                    command_factory=lambda: [
                        "docker",
                        "compose",
                        "up",
                        "-d",
                        "--build",
                        "--pull",
                        "missing",
                        "--wait",
                    ],
                    tee=False,
                ),
            ),
            (
                "status",
                Task(
                    description="Show current service status and health",
                    command_factory=lambda: ["docker", "compose", "ps"],
                    timed=False,
                    tee=False,
                ),
            ),
            (
                "dev",
                Task(
                    description="Start services + GUI (full development stack)",
                    command_factory=list,
                    tee=False,
                ),
            ),
            (
                "dev-vn",
                Task(
                    description="Start services + Ren'Py VN (visual novel stack)",
                    command_factory=list,
                    tee=False,
                ),
            ),
        ),
    ),
    (
        "Client Interfaces",
        (
            (
                "gui",
                Task(
                    description="Launch Pygame GUI (runs on host machine)",
                    command_factory=lambda: [
                        sys.executable,
                        "-m",
                        "hosts.gui",
                        "--agent",
                        "http://localhost:10000/",
                    ],
                    tee=False,
                ),
            ),
            (
                "cli",
                Task(
                    description="Launch terminal CLI client (runs on host machine)",
                    command_factory=_cli_command,
                    tee=False,
                ),
            ),
            (
                "vn",
                Task(
                    description="Launch Ren'Py Visual Novel GUI (runs on host machine)",
                    command_factory=_build_vn_command,
                    tee=False,
                ),
            ),
        ),
    ),
    (
        "Quality Gates",
        (
            (
                "fix",
                Task(
                    description="Run every auto-fixer; skip the check pass",
                    command_factory=lambda: [*python_script("scripts", "lint.py"), "--fix-only"],
                ),
            ),
            (
                "lint",
                Task(
                    description=(
                        "Run code quality checks (ruff format --check, ruff check, ty); "
                        "no mutation — use `make fix` to auto-format"
                    ),
                    command_factory=lambda: [*python_script("scripts", "lint.py"), "--check-only"],
                ),
            ),
            (
                "validate",
                Task(
                    description="Quick validation: lint + unit tests only (fast feedback)",
                    command_factory=lambda: python_script("scripts", "validate.py"),
                ),
            ),
            (
                "test",
                Task(
                    description="Run full test suite (unit + integration + performance)",
                    command_factory=lambda: python_script("scripts", "test.py"),
                ),
            ),
            (
                "test-unit",
                Task(
                    description="Run unit tests only (parallel with auto CPU detection)",
                    command_factory=lambda: [*python_script("scripts", "test.py"), "--unit"],
                ),
            ),
            (
                "test-integration",
                Task(
                    description="Run integration tests only (auto-starts containers)",
                    command_factory=lambda: [*python_script("scripts", "test.py"), "--integration"],
                ),
            ),
            (
                "test-performance",
                Task(
                    description="Run performance tests only",
                    command_factory=lambda: [*python_script("scripts", "test.py"), "--performance"],
                ),
            ),
            (
                "audit",
                Task(
                    description="Audit dependencies for security vulnerabilities",
                    command_factory=lambda: python_script("scripts", "audit.py"),
                ),
            ),
        ),
    ),
    (
        "Documentation",
        (
            (
                "docs",
                Task(
                    description="Serve project documentation (Zensical on http://localhost:8000)",
                    command_factory=lambda: ["zensical", "serve"],
                    tee=False,
                ),
            ),
        ),
    ),
    (
        "Observability",
        (
            (
                "observe",
                Task(
                    description="Open observability UIs in browser (Jaeger, Prometheus, Dozzle)",
                    command_factory=lambda: python_script("scripts", "observe.py"),
                    timed=False,
                ),
            ),
        ),
    ),
    (
        "Maintenance",
        (
            (
                "deps",
                Task(
                    description="Show dependency tree",
                    command_factory=lambda: python_script("scripts", "deps.py"),
                ),
            ),
            (
                "clean",
                Task(
                    description="Remove build artifacts, cache, and temp files",
                    command_factory=lambda: python_script("scripts", "clean_build.py"),
                ),
            ),
            (
                "clean-cache",
                Task(
                    description="Remove cache directories only",
                    command_factory=lambda: (
                        [*python_script("scripts", "clean_build.py"), "--cache-only"]
                    ),
                ),
            ),
            (
                "clean-tests",
                Task(
                    description="Remove test artifacts only",
                    command_factory=lambda: (
                        [*python_script("scripts", "clean_build.py"), "--tests-only"]
                    ),
                ),
            ),
            (
                "prune",
                Task(
                    description="Remove stopped containers, dangling images, unused build cache",
                    command_factory=lambda: ["docker", "system", "prune", "-f"],
                    tee=False,
                ),
            ),
        ),
    ),
)

TASKS = {name: task for _, group in TASK_GROUPS for name, task in group}

COMPOSITE_TASKS: dict[str, list[str]] = {
    "yolo": ["clean", "down", "setup", "upgrade", "clean"],
    "restart": ["down", "up"],
    "dev": ["down", "up", "gui"],
    "dev-vn": ["down", "up", "vn"],
    "rebuild": [],  # handled specially
}


def print_help() -> None:
    """Print supported commands."""
    print()
    print("Usage:")
    print("  uv run kourai-dev <command> [-- <args...>]")
    print("  make <command>  # optional compatibility wrapper")
    print()
    print("Commands:")
    for group_name, group in TASK_GROUPS:
        print(f"\n  {group_name}:")
        for name, task in group:
            print(f"    {name:<22} {task.description}")
    print()


def run_process(command: list[str], *, cwd: Path) -> int:
    """Direct passthrough for tee=False tasks (preserves stdin/TTY)."""
    try:
        result = subprocess.run(command, cwd=cwd, env=build_env(), check=False)
    except FileNotFoundError:
        print(f"Command not found: {command[0]}", file=sys.stderr)
        return 127
    return result.returncode


def _execute_task(task: Task, command: list[str], *, label: str) -> int:
    """Dispatch a leaf task by tee mode."""
    if task.tee:
        return run_step(command, check=False, label=label, cwd=task.cwd, env=build_env())
    return run_process(command, cwd=task.cwd)


def run_task(name: str, extra_args: list[str] | None = None) -> int:
    """Run a named task."""
    extra_args = strip_passthrough_marker(extra_args or [])

    if name == "help":
        print_help()
        return 0

    if COMPOSITE_TASKS.get(name):
        start = time.perf_counter()
        for task_name in COMPOSITE_TASKS[name]:
            result = run_task(task_name)
            if result != 0:
                elapsed = time.perf_counter() - start
                print(
                    f"[ERROR] Sub-step '{task_name}' failed with exit {result}; '{name}' aborted",
                    file=sys.stderr,
                )
                print(f"[TIMER] Target {name} aborted at '{task_name}' after {elapsed:.2f}s")
                return result
        elapsed = time.perf_counter() - start
        print(f"[TIMER] Target {name} completed in {elapsed:.2f}s")
        return 0

    if name == "rebuild":
        start = time.perf_counter()
        for task_name in ("down", "prune", "clean"):
            result = run_task(task_name)
            if result != 0:
                elapsed = time.perf_counter() - start
                print(
                    f"[ERROR] Sub-step '{task_name}' failed with exit "
                    f"{result}; rebuild aborted before docker build",
                    file=sys.stderr,
                )
                print(f"[TIMER] Target rebuild aborted at '{task_name}' after {elapsed:.2f}s")
                return result
        task = TASKS[name]
        result = _execute_task(task, task.command_factory() + extra_args, label=name)
        if result == 0:
            run_process(["docker", "compose", "ps"], cwd=task.cwd)
        elapsed = time.perf_counter() - start
        if result == 0:
            print(f"[TIMER] Target rebuild completed in {elapsed:.2f}s")
        else:
            print(
                f"[ERROR] docker compose build/up failed with exit {result}",
                file=sys.stderr,
            )
            print(f"[TIMER] Target rebuild aborted in build step after {elapsed:.2f}s")
        return result

    task = TASKS[name]
    command = task.command_factory() + extra_args
    start = time.perf_counter()
    result = _execute_task(task, command, label=name)
    if task.timed:
        elapsed = time.perf_counter() - start
        if result == 0:
            print(f"[TIMER] Target {name} completed in {elapsed:.2f}s")
        else:
            print(f"[TIMER] Target {name} failed (exit {result}) after {elapsed:.2f}s")
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="kourai-dev",
        description="Cross-platform developer entrypoints for Kourai Khryseai.",
    )
    parser.add_argument("command", nargs="?", default="help")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for the developer CLI."""
    configure_stdio()
    parsed = parse_args(argv or sys.argv[1:])

    if parsed.command not in TASKS and parsed.command != "help":
        print(f"Unknown command: {parsed.command}", file=sys.stderr)
        print_help()
        return 2

    if parsed.command in LOG_PURGING_COMMANDS:
        shutil.rmtree(PROJECT_ROOT / "logs", ignore_errors=True)

    # Open one DevLog session for the whole orchestration. Child scripts see
    # KOURAI_DEV_SESSION=1 in their env (set by build_env) and short-circuit.
    LOG.open(parsed.command)
    LOG.session_header(parsed.command, parsed.args or [])
    rc = 1
    try:
        rc = run_task(parsed.command, parsed.args)
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Operation cancelled by user", file=sys.stderr)
        rc = 130
    finally:
        LOG.session_footer(rc)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
