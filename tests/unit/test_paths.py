"""Unit tests for ``kourai_common.paths``.

Project-root + asset-directory accessors. Replaces the 9+ scattered
``Path(__file__).resolve().parents[N]`` traversals across hosts and shared.
The single-source-of-truth must:

- Resolve to the same directory every call.
- Walk up from ``__file__`` looking for ``pyproject.toml`` (matches the
  pattern already in ``hosts/vn/.../bridge.py``); robust under any
  directory restructure.
- Return real, on-disk directories for every accessor — these are
  cache + log + asset paths, not lazily-created hypotheticals.
"""

from __future__ import annotations

import pytest

from kourai_common.paths import (
    PROJECT_ROOT,
    assets_dir,
    audio_dir,
    avatars_dir,
    cache_dir,
    docs_assets_dir,
    find_project_root,
    logs_dir,
    templates_dir,
)


def test_project_root_contains_pyproject():
    assert (PROJECT_ROOT / "pyproject.toml").is_file()


def test_project_root_is_kourai_repo_root():
    # The repo's name is in the toml; checking the toml content guards against
    # a stray pyproject.toml in some sub-package being picked up first.
    text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "kourai-khryseai"' in text


def test_find_project_root_idempotent():
    assert find_project_root() == PROJECT_ROOT
    assert find_project_root() == find_project_root()


def test_assets_dir_exists():
    assert assets_dir().is_dir()
    assert assets_dir() == PROJECT_ROOT / "assets"


def test_logs_dir_resolves():
    # logs/ may not exist in a fresh checkout — the accessor returns the
    # path; callers create it as needed (matches existing log.py behavior).
    assert logs_dir() == PROJECT_ROOT / "logs"


def test_cache_dir_resolves():
    assert cache_dir() == PROJECT_ROOT / ".cache"


def test_templates_dir_resolves():
    assert templates_dir() == PROJECT_ROOT / "templates"


def test_docs_assets_dir_resolves():
    assert docs_assets_dir() == PROJECT_ROOT / "docs" / "assets"


def test_avatars_dir_anime():
    assert avatars_dir().is_dir()
    assert avatars_dir() == assets_dir() / "avatars" / "anime"
    # Default style is anime — matches CLI + GUI use.
    assert avatars_dir() == avatars_dir(style="anime")


def test_avatars_dir_vn():
    assert avatars_dir(style="vn").is_dir()
    assert avatars_dir(style="vn") == assets_dir() / "avatars" / "vn"


def test_avatars_dir_rejects_unknown_style():
    with pytest.raises(ValueError, match="unknown avatar style"):
        avatars_dir(style="claymation")


def test_audio_dir_music():
    assert audio_dir(kind="music").is_dir()
    assert audio_dir(kind="music") == assets_dir() / "audio" / "music"


def test_audio_dir_sfx():
    assert audio_dir(kind="sfx").is_dir()


def test_audio_dir_ambient():
    assert audio_dir(kind="ambient").is_dir()


def test_audio_dir_tts():
    # tts/ exists per asset layout (TTS cache dir).
    assert audio_dir(kind="tts") == assets_dir() / "audio" / "tts"


def test_audio_dir_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unknown audio kind"):
        audio_dir(kind="brainwaves")
