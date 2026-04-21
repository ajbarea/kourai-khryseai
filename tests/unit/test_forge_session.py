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
