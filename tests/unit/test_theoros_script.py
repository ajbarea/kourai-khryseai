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


@pytest.fixture(autouse=True)
def _isolated_skill_context(tmp_path, monkeypatch):
    """Point theoros.sh at a no-prerequisites skill-context fixture.

    Production `.claude/skill-context.md` gates `up` on a `docker compose ps`
    prerequisite that's never true in the unit-test runner. Tests that exercise
    specific prerequisite behavior (e.g. test_up_runs_prerequisites_and_aborts_on_failure)
    set their own override later in the test body — monkeypatch's last-write-wins
    semantics make that work without coordination.
    """
    fake_ctx = tmp_path / "skill-context.md"
    fake_ctx.write_text(
        "## theoros\n\n"
        "```yaml\n"
        "session_name: kourai-theoros\n"
        "repl_command: bash -c 'sleep 1'\n"
        "```\n"
    )
    monkeypatch.setenv("THEOROS_SKILL_CONTEXT_OVERRIDE", str(fake_ctx))


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
    result = _run("up", "--no-autopilot")
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
    assert _session_exists("kourai-theoros"), "tmux session not created"


def test_up_writes_state_file_with_required_fields(monkeypatch):
    monkeypatch.setenv("THEOROS_REPL_OVERRIDE", "bash -c 'while true; do sleep 1; done'")
    result = _run("up", "--no-autopilot")
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
    result = _run("up", "--no-autopilot")
    assert "tmux attach -t kourai-theoros -r" in result.stdout


def test_down_kills_session_and_removes_state_file(monkeypatch):
    monkeypatch.setenv("THEOROS_REPL_OVERRIDE", "bash -c 'while true; do sleep 1; done'")
    # up first
    up = _run("up", "--no-autopilot")
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


def _pane_count(session: str) -> int:
    result = subprocess.run(
        ["tmux", "list-panes", "-t", f"{session}:0", "-F", "#{pane_id}"],
        capture_output=True,
        text=True,
    )
    return len(result.stdout.strip().splitlines()) if result.returncode == 0 else 0


def test_up_creates_two_panes_when_ops_command_present(monkeypatch):
    """With ops_command in YAML/env, up creates a split layout (2 panes)."""
    monkeypatch.setenv("THEOROS_REPL_OVERRIDE", "bash -c 'while true; do sleep 1; done'")
    monkeypatch.setenv("THEOROS_OPS_OVERRIDE", "bash -c 'while true; do sleep 1; done'")
    result = _run("up", "--no-autopilot")
    assert result.returncode == 0, result.stderr
    assert _pane_count("kourai-theoros") == 2


def test_up_state_file_records_ops_pane(monkeypatch):
    monkeypatch.setenv("THEOROS_REPL_OVERRIDE", "bash -c 'while true; do sleep 1; done'")
    monkeypatch.setenv("THEOROS_OPS_OVERRIDE", "bash -c 'while true; do sleep 1; done'")
    result = _run("up", "--no-autopilot")
    assert result.returncode == 0, result.stderr
    state = json.loads(STATE_FILE.read_text())
    assert state["ops_pane"] == "kourai-theoros:0.1"


def test_up_refuses_when_session_exists(monkeypatch):
    monkeypatch.setenv("THEOROS_REPL_OVERRIDE", "bash -c 'while true; do sleep 1; done'")
    first = _run("up", "--no-autopilot")
    assert first.returncode == 0, first.stderr
    second = _run("up", "--no-autopilot")
    assert second.returncode != 0
    combined = second.stderr + second.stdout
    assert "already running" in combined
    assert "make theoros-down" in combined


def test_up_runs_prerequisites_and_aborts_on_failure(tmp_path, monkeypatch):
    """When a prerequisite command exits non-zero, up aborts with the named message."""
    fake_ctx = tmp_path / "skill-context.md"
    fake_ctx.write_text(
        "## theoros\n\n"
        "```yaml\n"
        "repl_command: bash -c 'sleep 1'\n"
        "session_name: kourai-theoros\n"
        "prerequisites:\n"
        "  - command: false\n"
        '    message: "intentional failure for the test"\n'
        "```\n"
    )
    monkeypatch.setenv("THEOROS_SKILL_CONTEXT_OVERRIDE", str(fake_ctx))
    result = _run("up", "--no-autopilot")
    assert result.returncode != 0
    assert "intentional failure for the test" in (result.stderr + result.stdout)
    # Session must NOT have been created.
    assert not _session_exists("kourai-theoros")


def test_makefile_exposes_theoros_targets():
    makefile = REPO_ROOT / "Makefile"
    text = makefile.read_text()
    for target in ("theoros:", "theoros-down:", "theoros-status:"):
        assert target in text, f"Makefile missing target: {target}"


def test_make_help_lists_theoros():
    """`make help` output should list the three theoros targets."""
    result = subprocess.run(
        ["make", "help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    for needle in ("theoros", "theoros-down", "theoros-status"):
        assert needle in result.stdout, f"`make help` does not surface '{needle}'"


def _tmux_option(session: str, option: str) -> str:
    """Read the effective tmux option value visible to a session.

    Uses -A so inherited global options surface (some options are set globally
    with `-g` for canonical 2026 propagation behavior; without -A they would
    return empty when queried per-session).
    """
    result = subprocess.run(
        ["tmux", "show-options", "-A", "-t", session, option],
        capture_output=True,
        text=True,
        check=True,
    )
    # tmux output form: "<option> <value>"
    parts = result.stdout.strip().split(None, 1)
    return parts[1] if len(parts) == 2 else ""


def test_up_enables_mouse_and_raises_scrollback(monkeypatch):
    """Up should set mouse on + history-limit 20000 for ergonomic spectating."""
    monkeypatch.setenv("THEOROS_REPL_OVERRIDE", "bash -c 'while true; do sleep 1; done'")
    result = _run("up", "--no-autopilot")
    assert result.returncode == 0, result.stderr

    assert _tmux_option("kourai-theoros", "mouse") == "on", (
        "mouse should be enabled for scroll / pane select / resize"
    )
    assert _tmux_option("kourai-theoros", "history-limit") == "50000", (
        "history-limit should be raised from tmux's 2000-line default "
        "(2026 balanced recommendation)"
    )


# --- Autopilot mode tests ---


def test_up_default_mode_requires_claude_on_path(monkeypatch):
    """Autopilot is on by default; missing `claude` binary fails fast.

    Sandboxed PATH that keeps /usr/bin and /bin (so the subprocess can find
    bash) but excludes user-local dirs where Claude Code typically installs
    (~/.local/bin or /usr/local/bin).
    """
    monkeypatch.setenv("THEOROS_REPL_OVERRIDE", "bash -c 'sleep 1'")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    if shutil.which("claude") is not None:
        pytest.skip("claude is installed in /usr/bin or /bin on this host; can't sandbox it out")
    result = _run("up")
    assert result.returncode != 0
    combined = result.stderr + result.stdout
    assert "Autopilot requires" in combined
    assert "claude" in combined.lower()


def test_no_autopilot_records_autopilot_zero_in_state_file(monkeypatch):
    """--no-autopilot is recorded as autopilot=0 + autopilot_pane=null."""
    monkeypatch.setenv("THEOROS_REPL_OVERRIDE", "bash -c 'while true; do sleep 1; done'")
    result = _run("up", "--no-autopilot")
    assert result.returncode == 0, result.stderr
    state = json.loads(STATE_FILE.read_text())
    assert state["autopilot"] == 0
    assert state["autopilot_pane"] is None


def test_no_autopilot_uses_two_pane_layout(monkeypatch):
    """--no-autopilot produces 2 panes (REPL + ops), not 3."""
    monkeypatch.setenv("THEOROS_REPL_OVERRIDE", "bash -c 'while true; do sleep 1; done'")
    monkeypatch.setenv("THEOROS_OPS_OVERRIDE", "bash -c 'while true; do sleep 1; done'")
    result = _run("up", "--no-autopilot")
    assert result.returncode == 0, result.stderr
    assert _pane_count("kourai-theoros") == 2


def test_autopilot_brief_exists():
    """The driver brief is required for autopilot mode."""
    brief = REPO_ROOT / "scripts" / "theoros_autopilot.md"
    assert brief.is_file(), f"missing autopilot brief: {brief}"
    text = brief.read_text(encoding="utf-8")
    assert "autopilot" in text.lower()
    assert "kourai-theoros:0.0" in text  # references the REPL pane
    assert "kourai-theoros:0.1" in text  # references its own pane
    assert "kourai-theoros:0.2" in text  # references the ops pane


def test_prompt_library_exists_and_has_curated_entries():
    """Golden-dataset prompt library required for autopilot's prompt loop."""
    library = REPO_ROOT / "tests" / "fixtures" / "theoros_prompts.md"
    assert library.is_file(), f"missing prompt library: {library}"
    text = library.read_text(encoding="utf-8")
    # 2026 best practice for golden datasets: ≥10 curated entries.
    p_count = sum(1 for i in range(1, 30) if f"P{i:02d}" in text)
    assert p_count >= 10, f"prompt library has {p_count} P-numbered entries, expected >= 10"
