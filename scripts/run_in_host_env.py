"""Run a host-side command inside a dedicated uv-managed environment.

This avoids cross-platform collisions with workspace `.venv` directories that may
have been created by a different OS or toolchain.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Determine the correct host environment directory to prevent Windows/WSL clashes.
# Host venv names match project venv names + "-host" suffix:
#   - Project .venv-win → Host .venv-win-host
#   - Project .venv-wsl → Host .venv-wsl-host
#   - Project .venv     → Host .venv-host
# All variations are covered by .gitignore/.dockerignore globs (.venv*/)
_env_name = os.environ.get("UV_PROJECT_ENVIRONMENT")
if _env_name:
    _env_name = f"{_env_name}-host"
elif "WSL_DISTRO_NAME" in os.environ:
    _env_name = ".venv-host-wsl"
elif os.name == "nt":
    _env_name = ".venv-host-win"
else:
    _env_name = ".venv-host"

HOST_ENV_DIR = ROOT / _env_name


def _bin_dir(env_dir: Path) -> Path:
    return env_dir / ("Scripts" if os.name == "nt" else "bin")


def _host_env() -> dict[str, str]:
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(HOST_ENV_DIR)
    path_parts = [str(_bin_dir(HOST_ENV_DIR))]
    if os.name == "nt":
        path_parts.insert(0, str(HOST_ENV_DIR))
    env["PATH"] = os.pathsep.join(path_parts + [env.get("PATH", "")])
    return env


def _run(command: list[str], *, env: dict[str, str] | None = None, check: bool = True) -> int:
    try:
        completed = subprocess.run(command, cwd=ROOT, env=env)  # noqa: S603
        if check and completed.returncode != 0:
            raise SystemExit(completed.returncode)
        return completed.returncode
    except KeyboardInterrupt:
        # User pressed Ctrl+C. Return exit code SIGINT (130)
        return 130


def _ensure_host_env() -> dict[str, str]:
    if not HOST_ENV_DIR.exists():
        _run(["uv", "venv", str(HOST_ENV_DIR)])

    env = _host_env()
    is_synced = _run(
        ["uv", "sync", "--active", "--all-packages", "--check"],
        env=env,
        check=False,
    )
    if is_synced != 0:
        _run(["uv", "sync", "--active", "--all-packages"], env=env)
    return env


def _resolve_command(command: list[str]) -> list[str]:
    resolved = command[:]
    if not resolved:
        return resolved

    executable = resolved[0].lower()
    if executable in {"python", "python.exe", "python3", "python3.exe"}:
        python_name = "python.exe" if os.name == "nt" else "python"
        resolved[0] = str(_bin_dir(HOST_ENV_DIR) / python_name)
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a command inside the dedicated host uv environment."
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to execute. Prefix with `--` to separate script options.",
    )
    args = parser.parse_args()

    command = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("missing command to run")

    env = _ensure_host_env()
    raise SystemExit(_run(_resolve_command(command), env=env, check=False))


if __name__ == "__main__":
    main()
