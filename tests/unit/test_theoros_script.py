"""Subprocess-based tests for scripts/theoros.sh."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

if shutil.which("tmux") is None:
    pytest.skip("tmux not available", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "theoros.sh"
STATE_FILE = Path("/tmp/kourai-theoros.state")


def _run(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def _kill_session_if_exists(name: str) -> None:
    subprocess.run(["tmux", "kill-session", "-t", name], capture_output=True)


def _session_exists(name: str) -> bool:
    result = subprocess.run(["tmux", "has-session", "-t", name], capture_output=True)
    return result.returncode == 0


@pytest.fixture(autouse=True)
def _clean():
    """Remove any leftover state file and tmux session before and after each test."""
    STATE_FILE.unlink(missing_ok=True)
    _kill_session_if_exists("kourai-theoros")
    yield
    STATE_FILE.unlink(missing_ok=True)
    _kill_session_if_exists("kourai-theoros")


def test_script_is_executable_via_bash():
    assert SCRIPT.is_file(), f"{SCRIPT} not found"


def test_status_reports_no_session_when_state_missing():
    result = _run("status")
    assert result.returncode == 0, result.stderr
    assert "No theoros session running" in result.stdout


def test_status_prints_state_file_when_present():
    STATE_FILE.write_text(
        json.dumps({"session": "kourai-theoros", "started_at": "2026-05-17T00:00:00Z"})
    )
    result = _run("status")
    assert result.returncode == 0, result.stderr
    assert "kourai-theoros" in result.stdout
    assert "started_at" in result.stdout


def test_unknown_subcommand_errors():
    result = _run("nonsense")
    assert result.returncode != 0
    assert "Usage" in result.stderr or "Usage" in result.stdout


def test_up_creates_tmux_session(monkeypatch):
    """Up creates a detached tmux session named per session_name."""
    # Override the skill-context REPL to something that does not depend on docker.
    monkeypatch.setenv("THEOROS_REPL_OVERRIDE", "bash -c 'while true; do sleep 1; done'")
    result = _run("up")
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
    assert _session_exists("kourai-theoros"), "tmux session not created"


def test_up_writes_state_file_with_required_fields(monkeypatch):
    monkeypatch.setenv("THEOROS_REPL_OVERRIDE", "bash -c 'while true; do sleep 1; done'")
    result = _run("up")
    assert result.returncode == 0, result.stderr
    assert STATE_FILE.is_file()
    state = json.loads(STATE_FILE.read_text())
    for key in (
        "session",
        "started_at",
        "cwd",
        "repl_pid",
        "attach_cmd",
        "driver_pane",
        "ops_pane",
    ):
        assert key in state, f"state file missing required key: {key}"
    assert isinstance(state["repl_pid"], int), "repl_pid should be a JSON integer, not a string"
    assert state["session"] == "kourai-theoros"


def test_up_prints_attach_instructions(monkeypatch):
    monkeypatch.setenv("THEOROS_REPL_OVERRIDE", "bash -c 'while true; do sleep 1; done'")
    result = _run("up")
    assert "tmux attach -t kourai-theoros -r" in result.stdout


def test_down_kills_session_and_removes_state_file(monkeypatch):
    monkeypatch.setenv("THEOROS_REPL_OVERRIDE", "bash -c 'while true; do sleep 1; done'")
    # up first
    up = _run("up")
    assert up.returncode == 0, up.stderr
    assert _session_exists("kourai-theoros")
    assert STATE_FILE.is_file()

    # down
    down = _run("down")
    assert down.returncode == 0, down.stderr
    assert not _session_exists("kourai-theoros")
    assert not STATE_FILE.exists()


def test_down_is_idempotent_when_no_session():
    """down on a stopped repo should be a no-op success."""
    result = _run("down")
    assert result.returncode == 0, result.stderr
