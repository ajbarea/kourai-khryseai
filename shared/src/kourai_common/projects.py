"""Player project registry — per-player workspaces under ~/.kourai_khryseai/projects/.

Each project is a real git repository on the player's disk. ProjectManager owns
the SQLite registry (the `projects` table in agent_memory.db) and the on-disk
layout. Forge sessions (worktrees) live one layer up — see forge_session.py.

This module deliberately stays free of agent-execution concerns. It only knows
about: create from template, list, get, delete.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from kourai_common.player_constants import PLAYER_DIR, _now_iso

if TYPE_CHECKING:
    import sqlite3

log = logging.getLogger(__name__)

PROJECTS_DIR = PLAYER_DIR / "projects"
TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"

KNOWN_TEMPLATES = ("empty", "python", "node", "backend", "frontend")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class ProjectError(Exception):
    """Raised on project-creation or lookup failures."""


@dataclass
class Project:
    project_id: str
    player_id: str
    name: str
    path: Path
    template: str | None
    created_at: str
    github_repo: str | None = None

    @property
    def main_branch(self) -> str:
        return "main"


def _slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    if not slug:
        raise ProjectError(f"Project name {name!r} produces an empty slug")
    return slug


def _get_db() -> sqlite3.Connection:
    """Reuse the shared agent_memory.db connection; ensure project tables exist."""
    from kourai_common.memory import _get_db as _shared_db

    conn = _shared_db()
    _ensure_tables(conn)
    return conn


_tables_initialized = False


def _ensure_tables(conn: sqlite3.Connection) -> None:
    global _tables_initialized
    if _tables_initialized:
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            project_id   TEXT PRIMARY KEY,
            player_id    TEXT NOT NULL,
            name         TEXT NOT NULL,
            path         TEXT NOT NULL,
            template     TEXT,
            created_at   TEXT NOT NULL,
            github_repo  TEXT,
            UNIQUE (player_id, name)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_player ON projects (player_id)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS forge_sessions (
            session_id  TEXT PRIMARY KEY,
            project_id  TEXT NOT NULL,
            branch      TEXT NOT NULL,
            workdir     TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'active',
            started_at  TEXT NOT NULL,
            ended_at    TEXT,
            FOREIGN KEY (project_id) REFERENCES projects (project_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_forge_sessions_project ON forge_sessions (project_id, status)"
    )
    conn.commit()
    _tables_initialized = True


def _row_to_project(row: tuple) -> Project:
    return Project(
        project_id=row[0],
        player_id=row[1],
        name=row[2],
        path=Path(row[3]),
        template=row[4],
        created_at=row[5],
        github_repo=row[6],
    )


def _git(cwd: Path, *args: str) -> None:
    """Run a git command; raise ProjectError on non-zero exit."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ProjectError(f"git {' '.join(args)} failed in {cwd}: {result.stderr.strip()}")


def _copy_template(template: str, dest: Path) -> None:
    """Copy a named template tree into dest. 'empty' is a no-op."""
    if template == "empty":
        return
    src = TEMPLATES_DIR / template
    if not src.is_dir():
        raise ProjectError(f"Unknown template {template!r}; expected one of {KNOWN_TEMPLATES}")
    shutil.copytree(src, dest, dirs_exist_ok=True)


class ProjectManager:
    """CRUD over per-player projects on disk + in agent_memory.db."""

    @staticmethod
    def create(player_id: str, name: str, template: str = "empty") -> Project:
        """Create a new project: scaffold template, git init, register in DB.

        Raises ProjectError on duplicate name, unknown template, or git failure.
        """
        if template not in KNOWN_TEMPLATES:
            raise ProjectError(f"Unknown template {template!r}; expected one of {KNOWN_TEMPLATES}")

        slug = _slugify(name)
        player_root = PROJECTS_DIR / player_id
        path = player_root / slug
        if path.exists():
            raise ProjectError(f"Project path already exists: {path}")

        conn = _get_db()
        existing = conn.execute(
            "SELECT 1 FROM projects WHERE player_id = ? AND name = ?",
            (player_id, name),
        ).fetchone()
        if existing:
            raise ProjectError(f"Player already has a project named {name!r}")

        path.mkdir(parents=True, exist_ok=True)
        try:
            _copy_template(template, path)
            _git(path, "init", "-q", "-b", "main")
            # Make sure git can attribute the initial commit even if user.name is unset.
            _git(path, "config", "user.email", "forge@kourai.local")
            _git(path, "config", "user.name", "Kourai Forge")
            _git(path, "add", "-A")
            # Allow empty for the 'empty' template so we always have an initial commit
            # for worktrees to branch from.
            _git(path, "commit", "--allow-empty", "-q", "-m", "Initial forge")
        except Exception:
            shutil.rmtree(path, ignore_errors=True)
            raise

        project_id = uuid4().hex
        created_at = _now_iso()
        conn.execute(
            """
            INSERT INTO projects (project_id, player_id, name, path, template, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, player_id, name, str(path), template, created_at),
        )
        conn.commit()

        log.info("Created project %s (%s) at %s", name, project_id[:8], path)
        return Project(
            project_id=project_id,
            player_id=player_id,
            name=name,
            path=path,
            template=template,
            created_at=created_at,
        )

    @staticmethod
    def list_for_player(player_id: str) -> list[Project]:
        """All projects belonging to a player, oldest first."""
        conn = _get_db()
        rows = conn.execute(
            """
            SELECT project_id, player_id, name, path, template, created_at, github_repo
            FROM projects
            WHERE player_id = ?
            ORDER BY created_at ASC
            """,
            (player_id,),
        ).fetchall()
        return [_row_to_project(r) for r in rows]

    @staticmethod
    def get(project_id: str) -> Project | None:
        conn = _get_db()
        row = conn.execute(
            """
            SELECT project_id, player_id, name, path, template, created_at, github_repo
            FROM projects WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()
        return _row_to_project(row) if row else None

    @staticmethod
    def find(player_id: str, name_or_id: str) -> Project | None:
        """Resolve by name first, then by project_id (full or 8-char prefix)."""
        conn = _get_db()
        row = conn.execute(
            """
            SELECT project_id, player_id, name, path, template, created_at, github_repo
            FROM projects WHERE player_id = ? AND name = ?
            """,
            (player_id, name_or_id),
        ).fetchone()
        if row:
            return _row_to_project(row)

        row = conn.execute(
            """
            SELECT project_id, player_id, name, path, template, created_at, github_repo
            FROM projects WHERE player_id = ? AND project_id LIKE ?
            """,
            (player_id, f"{name_or_id}%"),
        ).fetchone()
        return _row_to_project(row) if row else None

    @staticmethod
    def delete(project_id: str, *, purge_files: bool = False) -> None:
        """Remove the registry row. If purge_files, also rm -rf the project dir."""
        project = ProjectManager.get(project_id)
        if project is None:
            return

        conn = _get_db()
        conn.execute("DELETE FROM forge_sessions WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        conn.commit()

        if purge_files and project.path.exists():
            shutil.rmtree(project.path, ignore_errors=True)
            log.info("Purged project files at %s", project.path)
