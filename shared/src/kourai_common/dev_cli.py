"""Cross-platform developer entrypoints for Kourai Khryseai.

The canonical local workflow is:

    uv run kourai-dev <command> [-- <args...>]

The Makefile remains available as a thin compatibility wrapper, but this
module is the single source of truth for supported developer commands.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_ENV = {
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
    "LC_ALL": "en_US.UTF-8",
    "LANG": "en_US.UTF-8",
}
CommandFactory = Callable[[], list[str]]


@dataclass(frozen=True)
class Task:
    """Metadata describing a developer task."""

    description: str
    command_factory: CommandFactory
    timed: bool = True
    cwd: Path = PROJECT_ROOT


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

    # Isolate platform-specific virtual environments to prevent binary conflicts.
    wsl = os.environ.get("WSL_DISTRO_NAME")
    if sys.platform == "win32":
        expected_env = ".venv-wsl" if wsl else ".venv-win"
    else:
        expected_env = ".venv"

    configured_env = env.get("UV_PROJECT_ENVIRONMENT")
    if not configured_env:
        env["UV_PROJECT_ENVIRONMENT"] = expected_env
    elif sys.platform == "win32" and configured_env == ".venv":
        # Auto-correct stale/global shell settings that defeat split-env isolation.
        env["UV_PROJECT_ENVIRONMENT"] = expected_env

    return env


def strip_passthrough_marker(args: list[str]) -> list[str]:
    """Allow ``--`` before passthrough arguments."""
    if args[:1] == ["--"]:
        return args[1:]
    return args


def python_script(*parts: str) -> list[str]:
    """Build a command for a repository Python script.

    Uses ``uv run`` so the selected interpreter always matches
    ``UV_PROJECT_ENVIRONMENT`` (important for split-env Windows/WSL setups).
    """
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
                ),
            ),
            (
                "setup-artifacts",
                Task(
                    description="Create HF Storage Bucket for agent artifacts",
                    command_factory=lambda: python_script("scripts", "setup_buckets.py"),
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
                ),
            ),
            (
                "down",
                Task(
                    description="Stop all services and remove containers",
                    command_factory=lambda: ["docker", "compose", "down", "--remove-orphans"],
                ),
            ),
            (
                "restart",
                Task(
                    description="Restart all services (down + up)",
                    command_factory=list,
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
                ),
            ),
            (
                "status",
                Task(
                    description="Show current service status and health",
                    command_factory=lambda: ["docker", "compose", "ps"],
                    timed=False,
                ),
            ),
            (
                "dev",
                Task(
                    description="Start services + GUI (full development stack)",
                    command_factory=list,
                ),
            ),
            (
                "dev-vn",
                Task(
                    description="Start services + Ren'Py VN (visual novel stack)",
                    command_factory=list,
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
                ),
            ),
            (
                "cli",
                Task(
                    description="Launch terminal CLI client (runs on host machine)",
                    command_factory=lambda: [sys.executable, "-m", "hosts.cli"],
                ),
            ),
            (
                "vn",
                Task(
                    description="Launch Ren'Py Visual Novel GUI (runs on host machine)",
                    command_factory=lambda: [
                        str(PROJECT_ROOT / "hosts" / "vn" / "renpy-8.5.2-sdk" / "renpy.exe"),
                        str(PROJECT_ROOT / "hosts" / "vn" / "kourai_vn"),
                    ],
                ),
            ),
        ),
    ),
    (
        "Quality Gates",
        (
            (
                "lint",
                Task(
                    description="Run code quality checks (ruff format, ruff check, ty)",
                    command_factory=lambda: python_script("scripts", "lint.py"),
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
                ),
            ),
        ),
    ),
)

TASKS = {name: task for _, group in TASK_GROUPS for name, task in group}

# Composite tasks that chain other tasks
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
    """Run a subprocess and return its exit code."""
    try:
        result = subprocess.run(command, cwd=cwd, env=build_env(), check=False)
    except FileNotFoundError:
        print(f"Command not found: {command[0]}", file=sys.stderr)
        return 127
    return result.returncode


def run_task(name: str, extra_args: list[str] | None = None) -> int:
    """Run a named task."""
    extra_args = strip_passthrough_marker(extra_args or [])

    if name == "help":
        print_help()
        return 0

    # Composite tasks: chain subtasks
    if COMPOSITE_TASKS.get(name):
        start = time.perf_counter()
        for task_name in COMPOSITE_TASKS[name]:
            result = run_task(task_name)
            if result != 0:
                elapsed = round(time.perf_counter() - start)
                print(f"[TIMER] Target {name} completed in {elapsed} seconds")
                return result
        elapsed = round(time.perf_counter() - start)
        print(f"[TIMER] Target {name} completed in {elapsed} seconds")
        return 0

    # Rebuild is a special composite: prune + clean + docker build
    if name == "rebuild":
        start = time.perf_counter()
        for task_name in ("down", "prune", "clean"):
            result = run_task(task_name)
            if result != 0:
                elapsed = round(time.perf_counter() - start)
                print(f"[TIMER] Target rebuild completed in {elapsed} seconds")
                return result
        # Now run the actual docker build
        task = TASKS[name]
        result = run_process(task.command_factory() + extra_args, cwd=task.cwd)
        if result == 0:
            # Show status after rebuild
            run_process(["docker", "compose", "ps"], cwd=task.cwd)
        elapsed = round(time.perf_counter() - start)
        print(f"[TIMER] Target rebuild completed in {elapsed} seconds")
        return result

    task = TASKS[name]
    command = task.command_factory() + extra_args
    start = time.perf_counter()
    result = run_process(command, cwd=task.cwd)
    if task.timed:
        elapsed = round(time.perf_counter() - start)
        print(f"[TIMER] Target {name} completed in {elapsed} seconds")
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

    try:
        return run_task(parsed.command, parsed.args)
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Operation cancelled by user", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
