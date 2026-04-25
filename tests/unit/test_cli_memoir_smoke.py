"""Smoke test: real ForgeSession + real Memoir produces memoir.jsonl on disk."""

from __future__ import annotations

import shutil
import sqlite3

import pytest

from kourai_common import forge_session as fs_mod, projects as projects_mod
from kourai_common.federation.memoir import Memoir
from kourai_common.federation.memoir_schema import EntrySource, MemoirEntry
from kourai_common.forge_session import ForgeSession
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


def test_memoir_appears_in_real_forge_workdir():
    p = _make_project()
    s = ForgeSession.start(p, label="add login")

    memoir = Memoir(s.workdir)
    entry = MemoirEntry(
        scene_id="s1.t1",
        agent="kallos",
        source=EntrySource.SPECIALIST_PROPOSED,
        agent_proposed="lint suggestion",
    )
    memoir.append(entry)

    memoir_path = s.workdir / "memoir.jsonl"
    assert memoir_path.exists()

    contents = memoir_path.read_text(encoding="utf-8")
    assert "kallos" in contents
    assert "lint suggestion" in contents

    restored = list(memoir.entries())
    assert restored == [entry]


def test_memoir_survives_pipeline_writes():
    p = _make_project()
    s = ForgeSession.start(p)

    (s.workdir / "fake_specialist_output.py").write_text("print('hi')\n", encoding="utf-8")

    memoir = Memoir(s.workdir)
    memoir.append(
        MemoirEntry(
            scene_id="s1.t1",
            agent="kallos",
            source=EntrySource.SPECIALIST_PROPOSED,
            agent_proposed="lint suggestion",
        )
    )

    assert (s.workdir / "fake_specialist_output.py").exists()
    assert (s.workdir / "memoir.jsonl").exists()

    restored = list(memoir.entries())
    assert len(restored) == 1


def test_memoir_cleaned_up_on_session_discard():
    p = _make_project()
    s = ForgeSession.start(p)

    memoir = Memoir(s.workdir)
    memoir.append(
        MemoirEntry(
            scene_id="s1.t1",
            agent="kallos",
            source=EntrySource.SPECIALIST_PROPOSED,
            agent_proposed="lint suggestion",
        )
    )

    memoir_path = s.workdir / "memoir.jsonl"
    assert memoir_path.exists()

    s.discard()

    assert not s.workdir.exists()
    assert s.status == "discarded"
