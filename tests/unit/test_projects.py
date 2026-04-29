"""Tests for the player project registry."""

from __future__ import annotations

import shutil
import sqlite3
import subprocess

import pytest

from kourai_common import projects as projects_mod
from kourai_common.projects import ProjectError, ProjectManager, derive_project_id


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Isolated DB + projects dir for every test."""
    db_path = tmp_path / "test_memory.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)

    monkeypatch.setattr(projects_mod, "_get_db", lambda: _seed_db(conn))
    monkeypatch.setattr(projects_mod, "PROJECTS_DIR", tmp_path / "projects")
    # Tests run with the real templates dir from the repo, but we don't need it
    # for 'empty' and we copy the existing python template if present.
    yield conn
    conn.close()


def _seed_db(conn: sqlite3.Connection) -> sqlite3.Connection:
    projects_mod._tables_initialized = False
    projects_mod._ensure_tables(conn)
    return conn


def _git_skip_if_missing() -> None:
    if shutil.which("git") is None:
        pytest.skip("git not available")


def test_create_empty_project_initializes_git_repo():
    _git_skip_if_missing()
    p = ProjectManager.create("player-1", "hello world")
    assert p.path.exists()
    assert (p.path / ".git").is_dir()
    # initial commit exists
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=p.path, capture_output=True, text=True, check=True
    )
    assert "Initial forge" in log.stdout
    # main branch
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=p.path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert branch.stdout.strip() == "main"


def test_create_with_python_template_copies_files():
    _git_skip_if_missing()
    p = ProjectManager.create("player-1", "tplproj", template="python")
    assert (p.path / "pyproject.toml").exists()
    assert (p.path / "tests" / "test_smoke.py").exists()
    assert (p.path / ".gitignore").exists()


def test_create_rejects_unknown_template():
    with pytest.raises(ProjectError, match="Unknown template"):
        ProjectManager.create("player-1", "x", template="haskell")


def test_create_rejects_duplicate_name_for_same_player():
    _git_skip_if_missing()
    ProjectManager.create("player-1", "dup")
    with pytest.raises(ProjectError):
        ProjectManager.create("player-1", "dup")


def test_create_allows_same_name_for_different_players():
    _git_skip_if_missing()
    a = ProjectManager.create("player-1", "shared")
    b = ProjectManager.create("player-2", "shared")
    assert a.project_id != b.project_id
    assert a.path != b.path


def test_list_returns_player_projects_in_creation_order():
    _git_skip_if_missing()
    ProjectManager.create("player-1", "first")
    ProjectManager.create("player-1", "second")
    ProjectManager.create("player-2", "other")
    out = ProjectManager.list_for_player("player-1")
    assert [p.name for p in out] == ["first", "second"]


def test_find_by_name_and_by_id_prefix():
    _git_skip_if_missing()
    p = ProjectManager.create("player-1", "lookup")
    by_name = ProjectManager.find("player-1", "lookup")
    assert by_name is not None and by_name.project_id == p.project_id
    by_prefix = ProjectManager.find("player-1", p.project_id[:8])
    assert by_prefix is not None and by_prefix.project_id == p.project_id
    assert ProjectManager.find("player-1", "ghost") is None


def test_delete_removes_row_and_optionally_files(tmp_path):
    _git_skip_if_missing()
    p = ProjectManager.create("player-1", "trash")
    assert p.path.exists()

    ProjectManager.delete(p.project_id)
    assert ProjectManager.get(p.project_id) is None
    # files preserved by default
    assert p.path.exists()

    p2 = ProjectManager.create("player-1", "trash2")
    ProjectManager.delete(p2.project_id, purge_files=True)
    assert not p2.path.exists()


def test_slugify_collapses_whitespace_and_special_chars():
    _git_skip_if_missing()
    p = ProjectManager.create("player-1", "  Hello, World!! ")
    assert p.path.name == "hello-world"


def test_slug_empty_raises():
    with pytest.raises(ProjectError):
        ProjectManager.create("player-1", "!!!")


# ── derive_project_id ──────────────────────────────────────────────


def test_derive_project_id_returns_16_hex_chars(tmp_path):
    project_id = derive_project_id(tmp_path)
    assert len(project_id) == 16
    assert all(c in "0123456789abcdef" for c in project_id)


def test_derive_project_id_is_stable(tmp_path):
    """Same path → same id, every time."""
    a = derive_project_id(tmp_path)
    b = derive_project_id(tmp_path)
    assert a == b


def test_derive_project_id_normalises_trailing_slash(tmp_path):
    """Path with and without trailing separator hash to the same id."""
    bare = derive_project_id(str(tmp_path))
    with_slash = derive_project_id(f"{tmp_path}/")
    assert bare == with_slash


def test_derive_project_id_accepts_string_or_path(tmp_path):
    """str and Path inputs produce the same id."""
    from_str = derive_project_id(str(tmp_path))
    from_path = derive_project_id(tmp_path)
    assert from_str == from_path


def test_derive_project_id_resolves_relative_path(tmp_path, monkeypatch):
    """Relative paths resolve against cwd before hashing."""
    monkeypatch.chdir(tmp_path)
    sub = tmp_path / "sub"
    sub.mkdir()
    via_relative = derive_project_id("sub")
    via_absolute = derive_project_id(sub)
    assert via_relative == via_absolute


def test_derive_project_id_resolves_user_home(tmp_path, monkeypatch):
    """`~` is expanded so `~/foo` matches the absolute home path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "kourai_test_home"
    target.mkdir()
    via_tilde = derive_project_id("~/kourai_test_home")
    via_absolute = derive_project_id(target)
    assert via_tilde == via_absolute


def test_derive_project_id_different_paths_differ(tmp_path):
    a = tmp_path / "alpha"
    b = tmp_path / "beta"
    a.mkdir()
    b.mkdir()
    assert derive_project_id(a) != derive_project_id(b)


def test_derive_project_id_resolves_symlinks(tmp_path):
    """Two paths pointing at the same physical dir share an id."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    assert derive_project_id(real) == derive_project_id(link)
