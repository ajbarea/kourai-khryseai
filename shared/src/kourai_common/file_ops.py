"""Secure file operation utilities for Kourai agent file I/O.

All file operations performed by agent code (Techne, Kallos, etc.) should
route through this module so we have a single enforcement point for:

- Path escape detection (no ../../../etc/passwd tricks)
- Symlink resolution before trust
- Allowlist-based extension filtering
- Project root scoping

Usage
-----
    from kourai_common.file_ops import validate_file_path, PathViolation

    try:
        safe = validate_file_path("/home/aj/project", "src/main.py")
    except PathViolation as exc:
        # Reject the write, log the violation
        ...
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

# File extensions that agents are allowed to write.  Executable and
# shell-script extensions are excluded by default — add only if a
# specific agent has a documented need.
ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Python
        ".py",
        ".pyi",
        ".pyx",
        # Web
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".html",
        ".css",
        ".scss",
        ".svelte",
        # Config / data
        ".toml",
        ".yaml",
        ".yml",
        ".json",
        ".jsonc",
        ".env.example",
        ".ini",
        ".cfg",
        ".conf",
        # Docs
        ".md",
        ".rst",
        ".txt",
        # SQL / migrations
        ".sql",
        # Ren'Py
        ".rpy",
        # Other source
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".rb",
        ".lua",
        # Build / CI
        "Makefile",
        ".mk",
        ".dockerfile",
        "Dockerfile",
    }
)


class PathViolation(ValueError):
    """Raised when a requested file path violates safety rules."""


def validate_file_path(
    project_root: str | Path,
    requested_path: str | Path,
    *,
    allow_create: bool = True,
) -> Path:
    """Validate and resolve a file path to ensure it is inside project_root.

    Args:
        project_root: The trusted root directory.  All writes must land inside.
        requested_path: The path the agent wants to write (may be relative).
        allow_create: If False, require the file to already exist.

    Returns:
        The resolved absolute ``Path`` inside ``project_root``.

    Raises:
        PathViolation: If the path escapes the project root, resolves through
            a symlink that points outside, or has a disallowed extension.
    """
    root = Path(project_root).resolve()
    # Make relative paths relative to project_root
    candidate = Path(requested_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    # Resolve without requiring the file to exist (strict=False)
    # so we can check containment before creation.
    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        raise PathViolation(f"Cannot resolve path {requested_path!r}: {exc}") from exc

    # Primary containment check
    try:
        resolved.relative_to(root)
    except ValueError:
        raise PathViolation(
            f"Path escape detected: {requested_path!r} resolves to {resolved} "
            f"which is outside project root {root}"
        ) from None

    # Symlink safety: if the file already exists and is a symlink, ensure
    # the link target is also inside the project root.
    if resolved.is_symlink():
        link_target = resolved.readlink().resolve()
        try:
            link_target.relative_to(root)
        except ValueError:
            raise PathViolation(
                f"Symlink escape detected: {resolved} → {link_target} "
                f"which is outside project root {root}"
            ) from None

    # Extension allowlist
    suffix = resolved.suffix or resolved.name  # handle e.g. "Makefile" (no ext)
    if suffix not in ALLOWED_EXTENSIONS:
        raise PathViolation(
            f"Extension {suffix!r} is not in the allowed write list for agent file ops. "
            f"File: {resolved}"
        )

    # Existence check
    if not allow_create and not resolved.exists():
        raise PathViolation(f"File does not exist and allow_create=False: {resolved}")

    log.debug("validate_file_path OK: %s → %s", requested_path, resolved)
    return resolved


def is_safe_path(
    project_root: str | Path,
    requested_path: str | Path,
    *,
    allow_create: bool = True,
) -> bool:
    """Convenience wrapper — returns bool instead of raising.

    Use ``validate_file_path`` directly when you need the resolved path.
    """
    try:
        validate_file_path(project_root, requested_path, allow_create=allow_create)
        return True
    except PathViolation:
        return False
