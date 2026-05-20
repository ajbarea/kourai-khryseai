"""ForgeSession — wrap one forge run in a git worktree on a session branch.

A session is the atomic unit of agent work on a player project. It exists so:

- Concurrent sessions on the same project don't trample each other (each gets
  its own working tree).
- Players get a clean accept/discard decision point: discard restores the
  project to its prior state by deleting the worktree + branch.
- The accept path is a fast-forward merge into main, never a destructive op.

The on-disk layout for project P at /path/P is:

    /path/P/                         <- main repo, branch=main
    /path/P/.kourai/forges/<id>/     <- worktree on branch forge/<slug>

Sessions are also recorded in agent_memory.db so `/project status` can list
pending forges across CLI restarts.
"""

from __future__ import annotations

import contextlib
import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from kourai_common.player_constants import _now_iso
from kourai_common.projects import ProjectError, _get_db

if TYPE_CHECKING:
    from kourai_common.projects import Project

log = logging.getLogger(__name__)

FORGES_DIRNAME = ".kourai/forges"


class ForgeSessionError(ProjectError):
    """Raised on worktree create/accept/discard failures."""


@dataclass
class ForgeSession:
    session_id: str
    project_id: str
    branch: str
    workdir: Path
    status: str  # active | accepted | discarded
    started_at: str
    ended_at: str | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────

    @staticmethod
    def start(project: Project, label: str | None = None) -> ForgeSession:
        """Create a new worktree on a fresh `forge/<...>` branch.

        `label` is an optional human hint folded into the branch name.
        """
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        slug = _sanitize_branch_slug(label)
        branch = f"forge/{timestamp}-{slug}"
        session_id = uuid4().hex
        workdir = project.path / FORGES_DIRNAME / session_id
        workdir.parent.mkdir(parents=True, exist_ok=True)

        try:
            _git(project.path, "worktree", "add", "-q", "-b", branch, str(workdir))
        except subprocess.CalledProcessError as e:
            raise ForgeSessionError(f"git worktree add failed: {e.stderr or e.stdout}") from e

        # Specialist agents run inside containers as a different UID; group-write
        # lets them drop tool caches (e.g. .pytest_cache) into the worktree.
        # setgid propagates the group to any subdirs they create in turn.
        _grant_group_write(workdir)

        # Inherit identity from the parent repo so commits in the worktree
        # are attributed without prompting the player.
        _git(workdir, "config", "user.email", "forge@kourai.local")
        _git(workdir, "config", "user.name", "Kourai Forge")

        started_at = _now_iso()
        conn = _get_db()
        conn.execute(
            """
            INSERT INTO forge_sessions
                (session_id, project_id, branch, workdir, status, started_at)
            VALUES (?, ?, ?, ?, 'active', ?)
            """,
            (session_id, project.project_id, branch, str(workdir), started_at),
        )
        conn.commit()

        log.info("Forge session %s started on %s", session_id[:8], branch)

        # M15: set session contextvar so all subsequent log records from this
        # host process carry the forge session correlation key.
        from kourai_common.log import set_session_id

        set_session_id(session_id[:8])

        return ForgeSession(
            session_id=session_id,
            project_id=project.project_id,
            branch=branch,
            workdir=workdir,
            status="active",
            started_at=started_at,
        )

    def accept(self) -> None:
        """Fast-forward this session's branch into main and tear down the worktree.

        If the worktree has uncommitted changes (the specialist pipeline writes
        files but nothing in-pipeline runs ``git commit``), auto-commit them
        onto the forge branch first so the ff-merge has something to fast-
        forward to. Refuses if the branch can't be fast-forwarded (e.g. main
        moved ahead); the player can then discard or resolve manually.
        """
        if self.status != "active":
            raise ForgeSessionError(f"Session {self.session_id[:8]} is not active")

        project = self._project()

        # Auto-commit any pipeline writes that nobody committed. Staging -A
        # also catches deletions. Empty working tree → git commit exits
        # non-zero, which is fine (nothing to save).
        if _worktree_is_dirty(self.workdir):
            try:
                _git(self.workdir, "add", "-A")
                _git(
                    self.workdir,
                    "commit",
                    "-q",
                    "--no-gpg-sign",
                    "-m",
                    f"forge: {self.session_id[:8]} pipeline output",
                )
                log.info(
                    "Forge session %s auto-committed worktree changes",
                    self.session_id[:8],
                )
            except subprocess.CalledProcessError as e:
                raise ForgeSessionError(
                    f"Auto-commit in {self.workdir} failed: {e.stderr or e.stdout}"
                ) from e

        try:
            _git(project.path, "merge", "--ff-only", "-q", self.branch)
        except subprocess.CalledProcessError as e:
            raise ForgeSessionError(
                f"Fast-forward merge of {self.branch} failed: {e.stderr or e.stdout}"
            ) from e

        self._teardown(project, status="accepted")
        log.info("Forge session %s accepted", self.session_id[:8])

    def discard(self) -> None:
        """Delete the worktree + branch. Main branch is untouched."""
        if self.status != "active":
            raise ForgeSessionError(f"Session {self.session_id[:8]} is not active")
        project = self._project()
        self._teardown(project, status="discarded")
        log.info("Forge session %s discarded", self.session_id[:8])

    # ── Internals ──────────────────────────────────────────────────────

    def _project(self) -> Project:
        from kourai_common.projects import ProjectManager

        project = ProjectManager.get(self.project_id)
        if project is None:
            raise ForgeSessionError(f"Parent project {self.project_id[:8]} no longer exists")
        return project

    def _teardown(self, project: Project, *, status: str) -> None:
        """Remove the worktree, delete the branch, mark session ended."""
        # `git worktree remove --force` handles dirty trees on discard.
        try:
            _git(project.path, "worktree", "remove", "--force", str(self.workdir))
        except subprocess.CalledProcessError as e:
            log.warning("git worktree remove failed for %s: %s", self.workdir, e.stderr or e.stdout)
            shutil.rmtree(self.workdir, ignore_errors=True)
            with contextlib.suppress(subprocess.CalledProcessError):
                _git(project.path, "worktree", "prune")

        # Delete the branch unless it was already merged in (accept path).
        delete_flag = "-d" if status == "accepted" else "-D"
        with contextlib.suppress(subprocess.CalledProcessError):
            _git(project.path, "branch", delete_flag, self.branch)

        ended_at = _now_iso()
        conn = _get_db()
        conn.execute(
            "UPDATE forge_sessions SET status = ?, ended_at = ? WHERE session_id = ?",
            (status, ended_at, self.session_id),
        )
        conn.commit()
        self.status = status
        self.ended_at = ended_at


# ── Lookups ────────────────────────────────────────────────────────────


def list_active_sessions(project_id: str) -> list[ForgeSession]:
    """Return all sessions still in `active` status for a project."""
    conn = _get_db()
    rows = conn.execute(
        """
        SELECT session_id, project_id, branch, workdir, status, started_at, ended_at
        FROM forge_sessions
        WHERE project_id = ? AND status = 'active'
        ORDER BY started_at ASC
        """,
        (project_id,),
    ).fetchall()
    return [_row_to_session(r) for r in rows]


def get_session(session_id: str) -> ForgeSession | None:
    conn = _get_db()
    row = conn.execute(
        """
        SELECT session_id, project_id, branch, workdir, status, started_at, ended_at
        FROM forge_sessions WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()
    return _row_to_session(row) if row else None


def find_session(project_id: str, session_id_or_prefix: str) -> ForgeSession | None:
    conn = _get_db()
    row = conn.execute(
        """
        SELECT session_id, project_id, branch, workdir, status, started_at, ended_at
        FROM forge_sessions
        WHERE project_id = ? AND session_id LIKE ?
        ORDER BY started_at DESC
        LIMIT 1
        """,
        (project_id, f"{session_id_or_prefix}%"),
    ).fetchone()
    return _row_to_session(row) if row else None


def _row_to_session(row: tuple) -> ForgeSession:
    return ForgeSession(
        session_id=row[0],
        project_id=row[1],
        branch=row[2],
        workdir=Path(row[3]),
        status=row[4],
        started_at=row[5],
        ended_at=row[6],
    )


def _git(cwd: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, ["git", *args], output=result.stdout, stderr=result.stderr
        )


def _worktree_is_dirty(cwd: Path) -> bool:
    """Return True if the worktree has uncommitted changes or untracked files."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


# Allowed in branch slugs — lowercase letters, digits, hyphen. Anything
# else gets squashed to '-' so git's check-ref-format doesn't reject the
# `git worktree add -b forge/<slug>` call. A prompt containing a backtick
# can otherwise produce a slug like `please-add-a-function-`d` — git
# rejects that. Conservative whitelist over enumerating git's blocklist.
_SLUG_DISALLOWED = re.compile(r"[^a-z0-9-]+")


def _sanitize_branch_slug(label: str | None, max_len: int = 24) -> str:
    """Normalize ``label`` into a git-branch-safe slug.

    Lowercases, replaces every disallowed character (space, backtick,
    quote, slash, etc.) with a hyphen, collapses runs of hyphens, strips
    leading/trailing hyphens, truncates to ``max_len``, and strips any
    trailing hyphen the truncation produced. Empty / None input falls
    back to ``"session"`` so the branch name always ends up shaped like
    ``forge/<timestamp>-<slug>``.
    """
    raw = (label or "").strip().lower()
    cleaned = _SLUG_DISALLOWED.sub("-", raw)
    # Collapse runs of hyphens so 'a   b' → 'a-b' (not 'a---b').
    collapsed = re.sub(r"-+", "-", cleaned).strip("-")
    truncated = collapsed[:max_len].rstrip("-")
    return truncated or "session"


def _grant_group_write(root: Path) -> None:
    """Recursively give the owning group write access + setgid on every dir.

    ``git worktree add`` materializes the tree with the host user's umask
    (typically 022 → g-w). Specialist agents run inside Docker with a different
    UID but the same GID as the host mount, so they need ``g+w`` to write
    tool caches like ``.pytest_cache`` or apply fix patches.
    ``s`` on directories keeps the group consistent for anything created later.
    """
    import stat

    for path in (root, *root.rglob("*")):
        try:
            mode = path.stat().st_mode
        except FileNotFoundError:
            continue
        new_mode = mode | stat.S_IWGRP
        if path.is_dir():
            new_mode |= stat.S_ISGID | stat.S_IXGRP
        if new_mode != mode:
            with contextlib.suppress(PermissionError):
                path.chmod(new_mode)
