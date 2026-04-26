"""Tests for ForgeSession (worktree create / accept / discard)."""

from __future__ import annotations

import shutil
import sqlite3
import subprocess

import pytest

from kourai_common import forge_session as fs_mod, projects as projects_mod
from kourai_common.forge_session import (
    ForgeSession,
    ForgeSessionError,
    list_active_sessions,
)
from kourai_common.projects import ProjectManager


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    db_path = tmp_path / "test_memory.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)

    def _db() -> sqlite3.Connection:
        projects_mod._tables_initialized = False
        projects_mod._ensure_tables(conn)
        return conn

    monkeypatch.setattr(projects_mod, "_get_db", _db)
    monkeypatch.setattr(fs_mod, "_get_db", _db)
    monkeypatch.setattr(projects_mod, "PROJECTS_DIR", tmp_path / "projects")
    if shutil.which("git") is None:
        pytest.skip("git not available")
    yield conn
    conn.close()


def _make_project():
    return ProjectManager.create("player-1", "fs-test")


def test_start_creates_worktree_on_forge_branch():
    p = _make_project()
    s = ForgeSession.start(p, label="add login")
    assert s.workdir.exists()
    assert s.branch.startswith("forge/")
    # worktree branch is checked out
    out = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=s.workdir,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == s.branch
    # session is recorded
    assert any(x.session_id == s.session_id for x in list_active_sessions(p.project_id))


def test_discard_removes_worktree_and_branch():
    p = _make_project()
    s = ForgeSession.start(p)
    s.discard()
    assert not s.workdir.exists()
    branches = subprocess.run(
        ["git", "branch", "--list", s.branch],
        cwd=p.path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert branches.stdout.strip() == ""
    assert list_active_sessions(p.project_id) == []
    assert s.status == "discarded"


def test_accept_fast_forwards_into_main():
    p = _make_project()
    s = ForgeSession.start(p)

    # Make a commit in the worktree
    (s.workdir / "hello.txt").write_text("hi", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=s.workdir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add hello"], cwd=s.workdir, check=True)

    s.accept()

    # main now contains hello.txt
    assert (p.path / "hello.txt").read_text() == "hi"
    # worktree gone
    assert not s.workdir.exists()
    assert s.status == "accepted"


def test_double_resolve_raises():
    p = _make_project()
    s = ForgeSession.start(p)
    s.discard()
    with pytest.raises(ForgeSessionError):
        s.discard()


def test_accept_auto_commits_uncommitted_pipeline_writes():
    """Specialist pipeline writes files but nothing in-pipeline runs git commit.
    accept() must stage+commit them so the ff-merge actually lands them on main.
    """
    p = _make_project()
    s = ForgeSession.start(p)

    # Simulate Techne writing a file into the worktree without committing.
    (s.workdir / "greet.py").write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    s.accept()

    # Auto-committed + fast-forwarded into main
    assert (p.path / "greet.py").read_text().startswith("def greet()")
    assert s.status == "accepted"
    log = subprocess.run(
        ["git", "log", "--format=%s", "-1"],
        cwd=p.path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "forge:" in log.stdout  # default auto-commit subject
    assert s.session_id[:8] in log.stdout


def test_accept_fails_when_main_diverged():
    p = _make_project()
    s = ForgeSession.start(p)

    # Diverge main with an unrelated commit
    (p.path / "main_only.txt").write_text("m", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=p.path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "main side"], cwd=p.path, check=True)

    # And commit something in the worktree so the branches truly diverge
    (s.workdir / "branch_only.txt").write_text("b", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=s.workdir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "branch side"], cwd=s.workdir, check=True)

    with pytest.raises(ForgeSessionError, match="Fast-forward"):
        s.accept()


# ---------------------------------------------------------------------------
# _sanitize_branch_slug — Round 6 caught backticks slipping through
# ---------------------------------------------------------------------------


class TestSanitizeBranchSlug:
    """Branch slugs must satisfy ``git check-ref-format`` to avoid the
    ``git worktree add -b forge/<slug>`` call rejecting. Round 6 produced
    ``please-add-a-function-`d`` from a prompt with a backtick — the old
    logic only stripped spaces. Conservative whitelist ``[a-z0-9-]``
    handles every shell-meta and quote character at once."""

    def test_simple_label_lowercased_and_hyphenated(self):
        from kourai_common.forge_session import _sanitize_branch_slug

        assert _sanitize_branch_slug("Add a function") == "add-a-function"

    def test_backtick_replaced_with_hyphen(self):
        # The exact Round 6 case: prompt had a backtick.
        from kourai_common.forge_session import _sanitize_branch_slug

        result = _sanitize_branch_slug("please add a function `d`")
        assert "`" not in result
        assert result.startswith("please-add-a-function")

    def test_quotes_replaced(self):
        from kourai_common.forge_session import _sanitize_branch_slug

        # Single AND double quotes both get squashed.
        assert "'" not in _sanitize_branch_slug("don't break things")
        assert '"' not in _sanitize_branch_slug('"hello"')

    def test_runs_of_disallowed_chars_collapse_to_one_hyphen(self):
        from kourai_common.forge_session import _sanitize_branch_slug

        # 'a   b' → 'a-b', not 'a---b'
        assert _sanitize_branch_slug("a   b") == "a-b"
        assert _sanitize_branch_slug("a!@#b") == "a-b"

    def test_leading_trailing_hyphens_stripped(self):
        from kourai_common.forge_session import _sanitize_branch_slug

        assert _sanitize_branch_slug("  hello  ") == "hello"
        assert _sanitize_branch_slug("---hello---") == "hello"

    def test_empty_or_none_falls_back_to_session(self):
        from kourai_common.forge_session import _sanitize_branch_slug

        assert _sanitize_branch_slug(None) == "session"
        assert _sanitize_branch_slug("") == "session"
        assert _sanitize_branch_slug("   ") == "session"
        # Pure-disallowed input is also empty after sanitization.
        assert _sanitize_branch_slug("```") == "session"

    def test_truncated_to_max_len_without_trailing_hyphen(self):
        # Default 24-char cap — and no trailing hyphen left over from
        # a truncation that lands on a hyphen boundary.
        from kourai_common.forge_session import _sanitize_branch_slug

        result = _sanitize_branch_slug("abcdefghijklmnopqrstuvwxyz1234")
        assert len(result) <= 24
        # If truncation lands on a hyphen, it gets stripped.
        result2 = _sanitize_branch_slug("twelve-chars-then-cut-here-and-there")
        assert not result2.endswith("-")

    def test_all_lowercase(self):
        from kourai_common.forge_session import _sanitize_branch_slug

        # Even when input is uppercase, output is lowercase.
        assert _sanitize_branch_slug("ADD A FUNCTION") == "add-a-function"

    def test_only_alphanumeric_and_hyphen(self):
        # Property-style: every character in the output is in [a-z0-9-].
        from kourai_common.forge_session import _sanitize_branch_slug

        for label in [
            "weird !@#$%^&* chars",
            "newlines\nand\ttabs",
            "unicode: café résumé naïve",
            "shell: $(rm -rf /) ; rm -rf /",
            "/path/like/this",
            "\\back\\slashes\\too",
        ]:
            result = _sanitize_branch_slug(label)
            assert all(c.isalnum() or c == "-" for c in result), (
                f"label={label!r} → result={result!r} has bad chars"
            )
