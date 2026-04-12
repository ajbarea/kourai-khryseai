"""Tests for the cross-platform developer CLI."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from kourai_common import dev_cli

if TYPE_CHECKING:
    from pathlib import Path


def test_run_task_sets_utf8_defaults(monkeypatch) -> None:
    """Child processes should inherit the repo's UTF-8 defaults."""
    captured: dict[str, object] = {}

    def fake_run(command, cwd, env, check):  # type: ignore[no-untyped-def]
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        captured["check"] = check
        return SimpleNamespace(returncode=0)

    monkeypatch.delenv("PYTHONUTF8", raising=False)
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    monkeypatch.setattr(dev_cli.subprocess, "run", fake_run)

    assert dev_cli.run_task("prune") == 0
    assert captured["command"] == ["docker", "system", "prune", "-f"]
    assert captured["cwd"] == dev_cli.PROJECT_ROOT
    assert captured["check"] is False

    env = cast("dict[str, str]", captured["env"])
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_yolo_runs_clean_down_setup_upgrade_clean(monkeypatch) -> None:
    """The composite yolo task should run the five steps in order."""
    commands: list[list[str]] = []

    def fake_run_process(command: list[str], *, cwd: Path) -> int:
        commands.append(command)
        assert cwd == dev_cli.PROJECT_ROOT
        return 0

    monkeypatch.setattr(dev_cli, "run_process", fake_run_process)

    assert dev_cli.run_task("yolo") == 0

    # yolo = clean -> down -> setup -> upgrade -> clean
    def script(name):
        return [
            "uv",
            "run",
            "--no-active",
            "python",
            str(dev_cli.PROJECT_ROOT / "scripts" / name),
        ]

    assert commands == [
        script("clean_build.py"),
        ["docker", "compose", "down", "--remove-orphans"],
        script("setup.py"),
        script("upgrade.py"),
        script("clean_build.py"),
    ]


def test_restart_runs_down_then_up(monkeypatch) -> None:
    """The composite restart task should run down then up."""
    commands: list[list[str]] = []

    def fake_run_process(command: list[str], *, cwd: Path) -> int:
        commands.append(command)
        return 0

    monkeypatch.setattr(dev_cli, "run_process", fake_run_process)

    assert dev_cli.run_task("restart") == 0
    assert commands == [
        ["docker", "compose", "down", "--remove-orphans"],
        ["docker", "compose", "up", "-d", "--wait"],
    ]


def test_help_lists_canonical_workflow(capsys) -> None:
    """Help output should advertise the uv-first workflow."""
    dev_cli.print_help()
    output = capsys.readouterr().out

    assert "uv run kourai-dev <command>" in output
    assert "validate" in output
    assert "check-env" in output
    assert "rebuild" in output


def test_unknown_command_returns_2(capsys) -> None:
    """Unknown commands should print help and return exit code 2."""
    result = dev_cli.main(["nonexistent-command"])
    assert result == 2
    output = capsys.readouterr()
    assert "Unknown command" in output.err


def test_passthrough_args_forwarded(monkeypatch) -> None:
    """Extra args after -- should be appended to the command."""
    captured: dict[str, object] = {}

    def fake_run_process(command: list[str], *, cwd: Path) -> int:
        captured["command"] = command
        return 0

    monkeypatch.setattr(dev_cli, "run_process", fake_run_process)

    dev_cli.run_task("clean", ["--", "--cache-only"])
    cmd = captured["command"]
    assert isinstance(cmd, list)
    assert "--cache-only" in cmd


def test_build_env_sets_venv_for_platform(monkeypatch) -> None:
    """build_env should set UV_PROJECT_ENVIRONMENT based on platform."""
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)

    env = dev_cli.build_env()
    # Should have set some value for UV_PROJECT_ENVIRONMENT
    assert "UV_PROJECT_ENVIRONMENT" in env
    assert env["UV_PROJECT_ENVIRONMENT"] in (".venv", ".venv-win", ".venv-wsl")


def test_build_env_corrects_windows_plain_venv(monkeypatch) -> None:
    """Windows should not keep a stale plain .venv override."""
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", ".venv")
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.setattr(dev_cli.sys, "platform", "win32")

    env = dev_cli.build_env()
    assert env["UV_PROJECT_ENVIRONMENT"] == ".venv-win"
