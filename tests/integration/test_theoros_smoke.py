"""End-to-end smoke for `make theoros` lifecycle.

Marked as integration; requires tmux. Uses env overrides
(THEOROS_REPL_OVERRIDE, THEOROS_OPS_OVERRIDE, THEOROS_SKILL_CONTEXT_OVERRIDE)
so the smoke test is hermetic and does not depend on docker.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = Path("/tmp/kourai-theoros.state")


if shutil.which("tmux") is None:
    pytest.skip("tmux not available", allow_module_level=True)


def _session_exists() -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", "kourai-theoros"],
        capture_output=True,
    )
    return result.returncode == 0


def _kill():
    subprocess.run(["tmux", "kill-session", "-t", "kourai-theoros"], capture_output=True)


@pytest.fixture(autouse=True)
def _clean():
    _kill()
    STATE_FILE.unlink(missing_ok=True)
    yield
    _kill()
    STATE_FILE.unlink(missing_ok=True)


def test_make_theoros_lifecycle(tmp_path):
    """make theoros → state file written + session alive; make theoros-down → both gone."""
    # Hermetic: stub the REPL and ops command so the test does not depend on docker.
    # Also stub the skill-context to bypass prerequisites.
    fake_ctx = tmp_path / "skill-context.md"
    fake_ctx.write_text(
        "## theoros\n\n"
        "```yaml\n"
        "repl_command: make cli\n"
        "session_name: kourai-theoros\n"
        "ops_command: docker compose logs\n"
        "```\n"
    )

    env = {
        **os.environ,
        "THEOROS_REPL_OVERRIDE": "bash -c 'while IFS= read -r line; do echo \"echoed: $line\"; done'",
        "THEOROS_OPS_OVERRIDE": "bash -c 'while true; do sleep 1; done'",
        "THEOROS_SKILL_CONTEXT_OVERRIDE": str(fake_ctx),
    }

    # up — use the script directly with --no-autopilot to keep the smoke hermetic
    # (autopilot mode would launch a real `claude` CLI session, out of scope here).
    up = subprocess.run(
        ["bash", "scripts/theoros.sh", "up", "--no-autopilot"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    assert up.returncode == 0, f"stderr: {up.stderr}\nstdout: {up.stdout}"
    assert _session_exists()
    assert STATE_FILE.is_file()

    state = json.loads(STATE_FILE.read_text())
    assert state["session"] == "kourai-theoros"
    assert state["ops_pane"] == "kourai-theoros:0.1"

    # Send a line to the REPL pane, then capture to confirm round-trip.
    subprocess.run(
        ["tmux", "send-keys", "-t", "kourai-theoros:0.0", "hello", "Enter"],
        check=True,
    )
    time.sleep(0.5)  # let the echo run
    capture = subprocess.run(
        ["tmux", "capture-pane", "-t", "kourai-theoros:0.0", "-p", "-S", "-50"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "echoed: hello" in capture.stdout

    # status
    status = subprocess.run(
        ["make", "theoros-status"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    assert status.returncode == 0
    assert "kourai-theoros" in status.stdout

    # down
    down = subprocess.run(
        ["make", "theoros-down"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    assert down.returncode == 0, down.stderr
    assert not _session_exists()
    assert not STATE_FILE.exists()
