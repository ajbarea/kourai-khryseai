"""Subprocess-based tests for scripts/theoros.sh."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

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


@pytest.fixture(autouse=True)
def _clean_state():
    """Remove any leftover state file before and after each test."""
    STATE_FILE.unlink(missing_ok=True)
    yield
    STATE_FILE.unlink(missing_ok=True)


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
