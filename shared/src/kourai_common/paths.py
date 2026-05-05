"""Project-root + asset-directory accessors.

Single source of truth for paths into the kourai checkout. Replaces the
~9 `Path(__file__).resolve().parents[N]` traversals previously scattered
across hosts and shared (each fragile under any directory restructure).

`research(2026-05)`: `importlib.resources.files()` is the Python 2026
best practice for installed-package data, but kourai's assets aren't
packaged with the wheel — they live in the repo's top-level `assets/`
next to `pyproject.toml`. Pathlib walk-up looking for `pyproject.toml`
(the pattern already in `hosts/vn/.../bridge.py`) is the right fit;
this module canonicalizes it. Source: pythontutorials.net "How to Get
Project Root Path" (2026-04).

Note: VN's `bridge.py` deliberately keeps its own walk-up implementation
because Ren'Py packages its own Python and importing kourai_common from
inside the Ren'Py runtime needs sys.path gymnastics.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

_AVATAR_STYLES = frozenset({"anime", "vn"})
_AUDIO_KINDS = frozenset({"music", "sfx", "ambient", "tts"})


@lru_cache(maxsize=1)
def find_project_root() -> Path:
    """Walk parents from this file until the kourai workspace root is found.

    The workspace root is the pyproject.toml that declares
    ``[tool.uv.workspace]`` — uniquely the top-level kourai-khryseai
    pyproject. Member packages (``shared/``, ``hosts/cli/``, etc.) each
    carry their own pyproject.toml without that section, so a naïve "first
    pyproject.toml found" walk-up stops too early when called from a
    member.

    Cached after first call — the on-disk layout doesn't change at runtime.
    Raises FileNotFoundError if the walk reaches the filesystem root without
    finding a workspace pyproject (which would mean kourai_common is being
    run outside any kourai checkout — a packaging error worth surfacing
    loudly).
    """
    current = Path(__file__).resolve()
    for parent in current.parents:
        toml = parent / "pyproject.toml"
        if toml.is_file() and "[tool.uv.workspace]" in toml.read_text(encoding="utf-8"):
            return parent
    msg = (
        f"could not find a [tool.uv.workspace] pyproject.toml walking up from "
        f"{current}; kourai_common.paths needs the kourai repo layout intact."
    )
    raise FileNotFoundError(msg)


PROJECT_ROOT: Path = find_project_root()


def assets_dir() -> Path:
    return PROJECT_ROOT / "assets"


def cache_dir() -> Path:
    return PROJECT_ROOT / ".cache"


def logs_dir() -> Path:
    return PROJECT_ROOT / "logs"


def templates_dir() -> Path:
    return PROJECT_ROOT / "templates"


def docs_assets_dir() -> Path:
    """Image/asset files served by the docs site (separate from runtime assets)."""
    return PROJECT_ROOT / "docs" / "assets"


def avatars_dir(style: Literal["anime", "vn"] = "anime") -> Path:
    if style not in _AVATAR_STYLES:
        msg = f"unknown avatar style {style!r}; valid: {sorted(_AVATAR_STYLES)}"
        raise ValueError(msg)
    return assets_dir() / "avatars" / style


def audio_dir(kind: Literal["music", "sfx", "ambient", "tts"] = "music") -> Path:
    if kind not in _AUDIO_KINDS:
        msg = f"unknown audio kind {kind!r}; valid: {sorted(_AUDIO_KINDS)}"
        raise ValueError(msg)
    return assets_dir() / "audio" / kind
