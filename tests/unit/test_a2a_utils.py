"""Unit tests for kourai_common.a2a_utils.

Focus: ``project_root_from_context`` reads the worktree path from
``Message.metadata`` (the M7 Phase 5 home for forge context) and
translates host paths to the container's bind-mount mirror so the same
value works on both sides.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from kourai_common.a2a_utils import (
    _translate_to_container,
    get_message_metadata,
    project_root_from_context,
)


def _ctx_with_metadata(meta: dict | None) -> MagicMock:
    """Build a minimal RequestContext-shaped mock with the given metadata."""
    ctx = MagicMock()
    if meta is None:
        ctx.message = None
    else:
        ctx.message = MagicMock()
        ctx.message.metadata = meta
    return ctx


class TestProjectRootFromContext:
    def test_reads_metadata_value(self, tmp_path: Path) -> None:
        ctx = _ctx_with_metadata({"project_root": str(tmp_path)})
        assert project_root_from_context(ctx) == tmp_path

    def test_falls_back_to_cwd_when_metadata_missing(self) -> None:
        ctx = _ctx_with_metadata({})
        assert project_root_from_context(ctx) == Path.cwd()

    def test_falls_back_to_cwd_when_path_does_not_exist(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope-does-not-exist"
        ctx = _ctx_with_metadata({"project_root": str(missing)})
        assert project_root_from_context(ctx) == Path.cwd()

    def test_falls_back_to_cwd_when_no_message(self) -> None:
        assert project_root_from_context(_ctx_with_metadata(None)) == Path.cwd()

    def test_strips_whitespace(self, tmp_path: Path) -> None:
        ctx = _ctx_with_metadata({"project_root": f"  {tmp_path}  "})
        assert project_root_from_context(ctx) == tmp_path


class TestGetMessageMetadata:
    def test_returns_empty_dict_for_none_source(self) -> None:
        assert get_message_metadata(None) == {}

    def test_returns_empty_dict_for_empty_metadata(self) -> None:
        ctx = _ctx_with_metadata({})
        assert get_message_metadata(ctx) == {}

    def test_unwraps_dict_metadata(self) -> None:
        ctx = _ctx_with_metadata({"yolo": "on", "project_id": "abc123"})
        meta = get_message_metadata(ctx)
        assert meta == {"yolo": "on", "project_id": "abc123"}

    def test_returns_empty_when_message_metadata_is_none(self) -> None:
        ctx = MagicMock()
        ctx.message = MagicMock()
        ctx.message.metadata = None
        assert get_message_metadata(ctx) == {}


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

    def test_project_root_from_context_translates_host_path(self, tmp_path: Path) -> None:
        fake_home = tmp_path / "kourai"
        forge = fake_home / ".kourai_khryseai/projects/abc/hello/.kourai/forges/xyz"
        forge.mkdir(parents=True)
        ctx = _ctx_with_metadata(
            {"project_root": "/home/ajbar/.kourai_khryseai/projects/abc/hello/.kourai/forges/xyz"}
        )
        with patch("kourai_common.a2a_utils.Path.home", return_value=fake_home):
            assert project_root_from_context(ctx) == forge
