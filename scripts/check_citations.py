"""Mechanical CI check: every citation link resolves to an artifact file.

Runs in <1s with no LLM call. Pre-commit hook + CI gate.

Usage:
    uv run python scripts/check_citations.py [project_root]
    # Exit 0 = all citations resolved + artifacts well-formed
    # Exit 1 = at least one link missing or artifact malformed
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

# Citation-link patterns we recognize
_PY_CITE_RE = re.compile(r"docs/citations/([a-zA-Z0-9._-]+\.md)")
_MD_FOOTNOTE_RE = re.compile(r"\[docs/citations/([a-zA-Z0-9._-]+\.md)\]")


def _strip_md_code_fences(text: str) -> str:
    """Drop ```fenced``` blocks; illustrative example slugs in user-facing
    docs are documentation, not real citation references."""
    lines: list[str] = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append(line)
    return "".join(lines)


_REQUIRED_FRONTMATTER_KEYS = {
    "title",
    "authors",
    "year",
    "urls",
    "verified_at",
    "verified_by",
    "claim_supported",
}

_STALE_DAYS = 365


def _iter_source_files(root: Path) -> Iterator[Path]:
    """Yield .py / .md / .yml / .yaml files outside vendored, generated, or
    fixture paths. `architecture/` + `tests/` carry illustrative slugs that
    would false-positive against the live `docs/citations/` directory."""
    exclude_dirs = {
        ".venv",
        "node_modules",
        "build",
        "dist",
        ".git",
        "__pycache__",
        "site",
        "tests",
        "architecture",
    }
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in exclude_dirs for part in path.parts):
            continue
        if path.suffix in {".py", ".md", ".yml", ".yaml"}:
            yield path


def find_citation_links(files: Iterable[Path]) -> Iterator[tuple[str, Path]]:
    """Yield (artifact_filename, source_file) for each citation link found."""
    for src in files:
        try:
            text = src.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        if src.suffix == ".md":
            text = _strip_md_code_fences(text)
        for m in _PY_CITE_RE.finditer(text):
            yield m.group(1), src
        for m in _MD_FOOTNOTE_RE.finditer(text):
            yield m.group(1), src


def _validate_frontmatter(artifact_path: Path) -> list[str]:
    """Return a list of error strings for the artifact, or empty if OK."""
    errors: list[str] = []
    try:
        text = artifact_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError) as e:
        return [f"{artifact_path}: read error: {e}"]

    if not text.startswith("---\n"):
        return [f"{artifact_path}: missing YAML frontmatter delimiter"]
    end = text.find("\n---\n", 4)
    if end == -1:
        return [f"{artifact_path}: unterminated YAML frontmatter"]
    try:
        fm = yaml.safe_load(text[4:end])
    except yaml.YAMLError as e:
        return [f"{artifact_path}: malformed YAML frontmatter: {e}"]
    if not isinstance(fm, dict):
        return [f"{artifact_path}: frontmatter is not a mapping"]

    missing = _REQUIRED_FRONTMATTER_KEYS - set(fm.keys())
    if missing:
        errors.append(f"{artifact_path}: missing required keys: {sorted(missing)}")

    # Stale verified_at check
    verified_at = fm.get("verified_at")
    if verified_at:
        try:
            ts = dt.datetime.fromisoformat(verified_at)
            age = dt.datetime.now(dt.UTC) - ts
            if age.days > _STALE_DAYS:
                errors.append(
                    f"{artifact_path}: verified_at is stale ({age.days} days > {_STALE_DAYS}); re-run aletheia.verify_and_cite"
                )
        except (TypeError, ValueError) as e:
            errors.append(f"{artifact_path}: verified_at not ISO-8601: {e}")

    return errors


def check_project(project_root: Path) -> tuple[int, list[str]]:
    """Walk project_root, verify all citation links resolve and artifacts are well-formed."""
    errors: list[str] = []
    seen_artifacts: set[Path] = set()

    for artifact_name, source in find_citation_links(_iter_source_files(project_root)):
        artifact_path = project_root / "docs" / "citations" / artifact_name
        if not artifact_path.exists():
            errors.append(f"{source}: cites missing artifact docs/citations/{artifact_name}")
            continue
        if artifact_path not in seen_artifacts:
            errors.extend(_validate_frontmatter(artifact_path))
            seen_artifacts.add(artifact_path)

    return (1 if errors else 0, errors)


def main(argv: list[str]) -> int:
    project_root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    rc, errors = check_project(project_root)
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    if rc == 0:
        print(f"OK: all citation links in {project_root} resolve to well-formed artifacts.")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
