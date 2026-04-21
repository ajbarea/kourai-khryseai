"""Unit tests for kourai_common.a2a_utils.

Focus: parse_project_root accepts every injection shape the pipeline has used,
so specialists (Dokimasia, Techne, Kallos) always run in the forge worktree
instead of silently falling back to the Kourai repo cwd.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from kourai_common.a2a_utils import _translate_to_container, parse_project_root


class TestParseProjectRoot:
    def test_canonical_form(self, tmp_path: Path) -> None:
        text = f"[User]: do a thing\n\nProject root: {tmp_path}"
        assert parse_project_root(text) == tmp_path

    def test_bracket_tag_form(self, tmp_path: Path) -> None:
        """CLI injects this on the outbound prompt."""
        text = f"[project_root: {tmp_path}]\nmake me a greeter"
        assert parse_project_root(text) == tmp_path

    def test_legacy_project_settings_form(self, tmp_path: Path) -> None:
        """Older transcripts used this key; keep compatibility."""
        text = f"[User]: x\n\n[Project Settings]: root={tmp_path}"
        assert parse_project_root(text) == tmp_path

    def test_falls_back_to_cwd_when_missing(self) -> None:
        assert parse_project_root("nothing here") == Path.cwd()

    def test_falls_back_when_path_does_not_exist(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope-does-not-exist"
        text = f"Project root: {missing}"
        assert parse_project_root(text) == Path.cwd()

    def test_canonical_form_wins_when_both_present(self, tmp_path: Path) -> None:
        """Transcript that still has the bracket tag plus the canonical line
        (possible if a specialist echoes the user's prompt back) should
        resolve to the canonical path."""
        other = tmp_path / "other"
        other.mkdir()
        text = f"[project_root: {other}]\nProject root: {tmp_path}"
        assert parse_project_root(text) == tmp_path


class TestTranslateToContainer:
    def test_leaves_unrelated_paths_alone(self) -> None:
        assert _translate_to_container(Path("/var/elsewhere")) == Path("/var/elsewhere")

    def test_rewrites_host_prefix_to_current_home(self, tmp_path: Path) -> None:
        """Host paths under .kourai_khryseai get remapped to this process's HOME."""
        fake_home = tmp_path / "kourai"
        fake_home.mkdir()
        with patch("kourai_common.a2a_utils.Path.home", return_value=fake_home):
            result = _translate_to_container(
                Path("/home/ajbar/.kourai_khryseai/projects/abc/hello/.kourai/forges/xyz")
            )
        assert result == fake_home / ".kourai_khryseai/projects/abc/hello/.kourai/forges/xyz"

    def test_parse_project_root_translates_host_path(self, tmp_path: Path) -> None:
        """End-to-end: a host-style transcript resolves to the container-mounted path."""
        fake_home = tmp_path / "kourai"
        forge = fake_home / ".kourai_khryseai/projects/p1/hello"
        forge.mkdir(parents=True)
        with patch("kourai_common.a2a_utils.Path.home", return_value=fake_home):
            text = "Project root: /home/ajbar/.kourai_khryseai/projects/p1/hello"
            assert parse_project_root(text) == forge
