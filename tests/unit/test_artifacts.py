"""Unit tests for artifact storage module.

Tests the ArtifactStorage class without requiring hf-mount or network access.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from kourai_common.artifacts import ArtifactStorage

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def temp_artifacts_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for artifact storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def storage(temp_artifacts_dir: Path) -> Generator[ArtifactStorage, None, None]:
    """Create an ArtifactStorage instance with temp directory."""
    with patch("kourai_common.artifacts.AGENT_ARTIFACTS_DIR", temp_artifacts_dir):
        yield ArtifactStorage("test_agent")


class TestArtifactStorageInit:
    """Test ArtifactStorage initialization."""

    def test_init_creates_base_dir(self, temp_artifacts_dir: Path) -> None:
        """Test that __init__ creates the base directory."""
        with patch("kourai_common.artifacts.AGENT_ARTIFACTS_DIR", temp_artifacts_dir):
            storage = ArtifactStorage("dokimasia")
            assert temp_artifacts_dir.exists()
            assert storage.agent_name == "dokimasia"

    def test_init_handles_permission_error(self, storage: ArtifactStorage) -> None:
        """Test that __init__ gracefully handles permission errors."""
        with patch("pathlib.Path.mkdir", side_effect=PermissionError("Access denied")):
            # Should not raise, but log warning and use fallback
            result = ArtifactStorage("test_agent")
            assert result.base_dir.name in ("kourai-artifacts-fallback", "kourai-artifacts")


class TestSaveArtifact:
    """Test artifact saving."""

    def test_save_json_artifact(self, storage: ArtifactStorage) -> None:
        """Test saving a dictionary as JSON."""
        data = {"passed": 100, "failed": 5, "duration": 23.4}
        path = storage.save_artifact("test_reports", data, name="run_001")

        assert path.exists()
        assert path.suffix == ".json"
        assert json.loads(path.read_text()) == data

    def test_save_text_artifact(self, storage: ArtifactStorage) -> None:
        """Test saving a string as text."""
        text = "Debug trace output\nLine 2\nLine 3"
        path = storage.save_artifact("debug_traces", text, name="trace_001")

        assert path.exists()
        assert path.suffix == ".txt"
        assert path.read_text() == text

    def test_save_bytes_artifact(self, storage: ArtifactStorage) -> None:
        """Test saving bytes."""
        data = b"\x89PNG\r\n\x1a\n"  # PNG header
        path = storage.save_artifact("binaries", data, name="image_001")

        assert path.exists()
        assert path.suffix == ".bin"
        assert path.read_bytes() == data

    def test_save_with_auto_name(self, storage: ArtifactStorage) -> None:
        """Test auto-generated filename with timestamp."""
        path = storage.save_artifact("test_reports", {"status": "ok"})

        assert path.exists()
        # Name should contain artifact_type and be in ISO format
        assert "test_reports_" in path.name

    def test_save_with_metadata(self, storage: ArtifactStorage) -> None:
        """Test saving artifact with metadata."""
        data = {"passed": 10}
        metadata = {"run_id": "abc123", "branch": "main"}
        path = storage.save_artifact("test_reports", data, name="run_001", metadata=metadata)

        assert path.exists()
        metadata_path = path.parent / "run_001.metadata.json"
        assert metadata_path.exists()

        saved_metadata = json.loads(metadata_path.read_text())
        assert saved_metadata["run_id"] == "abc123"
        assert saved_metadata["branch"] == "main"
        assert saved_metadata["agent"] == "test_agent"
        assert "saved_at" in saved_metadata

    def test_save_creates_subdirectory(self, storage: ArtifactStorage) -> None:
        """Test that save_artifact creates artifact type directories."""
        path = storage.save_artifact("custom_type", "content", name="file_001")

        artifact_dir = storage.base_dir / "custom_type"
        assert artifact_dir.exists()
        assert path.parent == artifact_dir


class TestLoadArtifact:
    """Test artifact loading."""

    def test_load_json_artifact(self, storage: ArtifactStorage) -> None:
        """Test loading a JSON artifact."""
        original = {"passed": 100, "failed": 5}
        storage.save_artifact("test_reports", original, name="run_001")

        loaded = storage.load_artifact("test_reports", "run_001")
        assert loaded == original

    def test_load_text_artifact(self, storage: ArtifactStorage) -> None:
        """Test loading a text artifact."""
        original = "Hello\nWorld"
        storage.save_artifact("logs", original, name="log_001")

        loaded = storage.load_artifact("logs", "log_001")
        assert loaded == original

    def test_load_bytes_artifact(self, storage: ArtifactStorage) -> None:
        """Test loading a bytes artifact."""
        original = b"binary data \x00\xff"
        storage.save_artifact("binaries", original, name="data_001")

        loaded = storage.load_artifact("binaries", "data_001")
        assert loaded == original

    def test_load_nonexistent_raises_error(self, storage: ArtifactStorage) -> None:
        """Test that loading nonexistent artifact raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Artifact not found"):
            storage.load_artifact("nonexistent", "missing_artifact")

    def test_load_prioritizes_json(self, storage: ArtifactStorage) -> None:
        """Test that load prioritizes .json over other formats."""
        artifact_dir = storage.base_dir / "test_type"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        # Save both JSON and text with same stem
        json_data = {"format": "json"}
        (artifact_dir / "artifact.json").write_text(json.dumps(json_data))
        (artifact_dir / "artifact.txt").write_text("text content")

        loaded = storage.load_artifact("test_type", "artifact")
        assert loaded == json_data


class TestListArtifacts:
    """Test artifact listing."""

    def test_list_empty(self, storage: ArtifactStorage) -> None:
        """Test listing when no artifacts exist."""
        result = storage.list_artifacts("empty_type")
        assert result == []

    def test_list_artifacts(self, storage: ArtifactStorage) -> None:
        """Test listing saved artifacts."""
        storage.save_artifact("test_reports", {"a": 1}, name="run_001")
        storage.save_artifact("test_reports", {"b": 2}, name="run_002")
        storage.save_artifact("test_reports", {"c": 3}, name="run_003")

        result = storage.list_artifacts("test_reports")
        assert sorted(result) == ["run_001", "run_002", "run_003"]

    def test_list_ignores_metadata_files(self, storage: ArtifactStorage) -> None:
        """Test that list_artifacts doesn't include .metadata.json files."""
        storage.save_artifact(
            "test_reports",
            {"data": "value"},
            name="run_001",
            metadata={"key": "val"},
        )

        result = storage.list_artifacts("test_reports")
        assert result == ["run_001"]
        # Metadata file should not be in the list
        assert all(".metadata" not in item for item in result)

    def test_list_sorted_chronologically(self, storage: ArtifactStorage) -> None:
        """Test that list returns artifacts sorted alphabetically."""
        names = ["run_003", "run_001", "run_002"]
        for name in names:
            storage.save_artifact("reports", {"n": name}, name=name)

        result = storage.list_artifacts("reports")
        assert result == ["run_001", "run_002", "run_003"]


class TestDeleteArtifact:
    """Test artifact deletion."""

    def test_delete_artifact(self, storage: ArtifactStorage) -> None:
        """Test deleting an artifact."""
        path = storage.save_artifact("test_reports", {"data": 1}, name="run_001")
        assert path.exists()

        result = storage.delete_artifact("test_reports", "run_001")
        assert result is True
        assert not path.exists()

    def test_delete_nonexistent_returns_false(self, storage: ArtifactStorage) -> None:
        """Test that deleting nonexistent artifact returns False."""
        result = storage.delete_artifact("nonexistent", "missing")
        assert result is False

    def test_delete_removes_metadata(self, storage: ArtifactStorage) -> None:
        """Test that delete also removes metadata files."""
        storage.save_artifact("reports", {"data": 1}, name="run_001", metadata={"key": "val"})

        artifact_dir = storage.base_dir / "reports"
        metadata_path = artifact_dir / "run_001.metadata.json"
        assert metadata_path.exists()

        storage.delete_artifact("reports", "run_001")
        assert not metadata_path.exists()


class TestArtifactsPath:
    """Test artifacts_path property."""

    def test_artifacts_path_property(self, storage: ArtifactStorage) -> None:
        """Test that artifacts_path returns the base directory."""
        assert storage.artifacts_path == storage.base_dir


class TestSummary:
    """Test summary generation."""

    def test_summary_empty(self, storage: ArtifactStorage) -> None:
        """Test summary when no artifacts exist."""
        result = storage.summary()
        assert result["agent"] == "test_agent"
        assert result["artifacts_path"] == str(storage.base_dir)
        assert result["types"] == {}

    def test_summary_with_artifacts(self, storage: ArtifactStorage) -> None:
        """Test summary with multiple artifact types."""
        storage.save_artifact("test_reports", {"a": 1}, name="run_001")
        storage.save_artifact("test_reports", {"b": 2}, name="run_002")
        storage.save_artifact("debug_traces", "trace data", name="trace_001")

        result = storage.summary()
        assert result["agent"] == "test_agent"
        assert result["types"]["test_reports"] == 2
        assert result["types"]["debug_traces"] == 1


class TestSpecialCharacters:
    """Test handling of special characters in content."""

    def test_save_unicode_content(self, storage: ArtifactStorage) -> None:
        """Test saving Unicode content."""
        text = "Hëllö Wørld 🚀 日本語"
        storage.save_artifact("logs", text, name="unicode_001")

        loaded = storage.load_artifact("logs", "unicode_001")
        assert loaded == text

    def test_save_json_with_special_chars(self, storage: ArtifactStorage) -> None:
        """Test saving JSON with special characters."""
        data = {"emoji": "🎉", "unicode": "Ñoño", "quotes": 'He said "hi"'}
        storage.save_artifact("data", data, name="special_001")

        loaded = storage.load_artifact("data", "special_001")
        assert loaded == data
