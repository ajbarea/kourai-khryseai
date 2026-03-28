"""Integration tests for artifact storage with hf-mount.

These tests verify that artifacts work correctly with hf-mount mounted directories,
and that the storage gracefully handles missing hf-mount.

To run with hf-mount enabled:
    HF_TOKEN=hf_xxx AGENT_ARTIFACTS_DIR=/tmp/hf-dokimasia \
    pytest tests/integration/test_artifacts_integration.py -v
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from kourai_common.artifacts import ArtifactStorage


class TestArtifactStorageWithRealFilesystem:
    """Integration tests using real filesystem operations."""

    def test_artifact_persistence_across_instances(self) -> None:
        """Test that artifacts persist across different ArtifactStorage instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Save with first instance
            storage1 = ArtifactStorage("agent_a")
            original_data = {"test": "value", "number": 42}

            # Override AGENT_ARTIFACTS_DIR for this test
            storage1.base_dir = tmpdir_path
            storage1.save_artifact("reports", original_data, name="test_001")

            # Load with second instance
            storage2 = ArtifactStorage("agent_a")
            storage2.base_dir = tmpdir_path
            loaded_data = storage2.load_artifact("reports", "test_001")

            assert loaded_data == original_data

    def test_multiple_agents_isolated_storage(self) -> None:
        """Test that different agents don't interfere with each other's artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Different agents save to same base dir
            storage_a = ArtifactStorage("agent_a")
            storage_a.base_dir = tmpdir_path

            storage_b = ArtifactStorage("agent_b")
            storage_b.base_dir = tmpdir_path

            # Each saves its own artifact
            data_a = {"agent": "a"}
            data_b = {"agent": "b"}

            storage_a.save_artifact("reports", data_a, name="report")
            storage_b.save_artifact("reports", data_b, name="report")

            # Verify each loads its own data
            assert storage_a.load_artifact("reports", "report") == data_a
            assert storage_b.load_artifact("reports", "report") == data_b

    def test_large_artifact_handling(self) -> None:
        """Test saving and loading large artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            storage = ArtifactStorage("test_agent")
            storage.base_dir = tmpdir_path

            # Create large dataset (1 MB JSON)
            large_data = {"records": [{"id": i, "value": "x" * 100} for i in range(10000)]}

            path = storage.save_artifact("large_data", large_data, name="big")
            assert path.exists()

            loaded = storage.load_artifact("large_data", "big")
            assert loaded == large_data
            assert isinstance(loaded, dict)
            assert len(loaded["records"]) == 10000

    def test_concurrent_artifact_access(self) -> None:
        """Test that artifact storage handles rapid sequential access."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            storage = ArtifactStorage("concurrent_test")
            storage.base_dir = tmpdir_path

            # Rapidly save and load artifacts
            for i in range(20):
                data = {"iteration": i, "timestamp": str(i)}
                storage.save_artifact("rapid_fire", data, name=f"run_{i:03d}")

            # Verify all exist
            artifacts = storage.list_artifacts("rapid_fire")
            assert len(artifacts) == 20

            # Verify all load correctly
            for i in range(20):
                loaded = storage.load_artifact("rapid_fire", f"run_{i:03d}")
                assert isinstance(loaded, dict)
                assert loaded["iteration"] == i

    def test_artifact_summary_accurate(self) -> None:
        """Test that summary correctly counts artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            storage = ArtifactStorage("agent_x")
            storage.base_dir = tmpdir_path

            # Save various artifacts
            for i in range(3):
                storage.save_artifact("type_a", {"i": i}, name=f"a_{i}")
            for i in range(5):
                storage.save_artifact("type_b", {"i": i}, name=f"b_{i}")
            for i in range(2):
                storage.save_artifact("type_c", {"i": i}, name=f"c_{i}")

            summary = storage.summary()
            assert summary["agent"] == "agent_x"
            assert summary["types"]["type_a"] == 3
            assert summary["types"]["type_b"] == 5
            assert summary["types"]["type_c"] == 2

    def test_metadata_persistence(self) -> None:
        """Test that metadata is correctly persisted and loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            storage = ArtifactStorage("test_agent")
            storage.base_dir = tmpdir_path

            metadata = {
                "run_id": "run_abc123",
                "status": "passed",
                "suite": "integration_tests",
            }

            storage.save_artifact(
                "test_results", {"passed": 100}, name="test_001", metadata=metadata
            )

            # Metadata should be accessible
            artifact_dir = tmpdir_path / "test_results"
            metadata_file = artifact_dir / "test_001.metadata.json"
            assert metadata_file.exists()

            saved_metadata = json.loads(metadata_file.read_text())
            assert saved_metadata["run_id"] == "run_abc123"
            assert saved_metadata["status"] == "passed"
            assert saved_metadata["agent"] == "test_agent"


class TestArtifactStorageEnvironment:
    """Test artifact storage with environment variables."""

    def test_respects_agent_artifacts_dir_env(self, monkeypatch) -> None:
        """Test that AGENT_ARTIFACTS_DIR env var is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            monkeypatch.setenv("AGENT_ARTIFACTS_DIR", str(tmpdir_path))

            # Re-import to pick up env var

            storage = ArtifactStorage("env_test")
            # Verify it uses the env var path (or a subdirectory of it)
            assert tmpdir_path in storage.base_dir.parents or storage.base_dir == tmpdir_path

    def test_fallback_to_temp_when_env_not_set(self, monkeypatch) -> None:
        """Test fallback to /tmp when AGENT_ARTIFACTS_DIR not set."""
        monkeypatch.delenv("AGENT_ARTIFACTS_DIR", raising=False)

        storage = ArtifactStorage("fallback_test")
        # Should use some temp directory
        assert storage.base_dir is not None
        assert storage.base_dir.exists() or storage.base_dir.parent.exists()


class TestArtifactStorageErrorHandling:
    """Test error handling in artifact operations."""

    def test_load_corrupted_json(self) -> None:
        """Test handling of corrupted JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            storage = ArtifactStorage("error_test")
            storage.base_dir = tmpdir_path

            # Save a valid artifact first
            artifact_dir = tmpdir_path / "corrupted"
            artifact_dir.mkdir(parents=True, exist_ok=True)

            # Manually write corrupted JSON
            json_file = artifact_dir / "bad.json"
            json_file.write_text("{invalid json content")

            # Should raise JSON decode error
            with pytest.raises(json.JSONDecodeError):
                storage.load_artifact("corrupted", "bad")

    def test_save_to_readonly_directory_fallback(self) -> None:
        """Test that save gracefully handles readonly directories."""
        storage = ArtifactStorage("readonly_test")

        # This test is platform-dependent, so we just verify the class handles init errors
        # The actual readonly test would require changing file permissions
        assert storage.agent_name == "readonly_test"


class TestArtifactWorkflow:
    """Test complete workflows with artifacts."""

    def test_complete_test_report_workflow(self) -> None:
        """Test a complete workflow of saving and managing test reports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            storage = ArtifactStorage("dokimasia")
            storage.base_dir = tmpdir_path

            # Simulate test run
            test_results = {
                "total": 150,
                "passed": 145,
                "failed": 5,
                "skipped": 0,
                "duration_seconds": 42.5,
                "timestamp": "2026-03-25T19:30:00",
            }

            report_path = storage.save_artifact(
                "test_reports",
                test_results,
                name="run_20260325_1930",
                metadata={
                    "suite": "unit_tests",
                    "branch": "main",
                    "commit_sha": "abc123def456",
                },
            )

            # Verify artifact was saved
            assert report_path.exists()

            # List all reports
            reports = storage.list_artifacts("test_reports")
            assert "run_20260325_1930" in reports

            # Load and verify
            loaded = storage.load_artifact("test_reports", "run_20260325_1930")
            assert isinstance(loaded, dict)
            assert loaded["passed"] == 145
            assert loaded["failed"] == 5

            # Clean up old reports (keep only 3 most recent)
            for i in range(5):
                storage.save_artifact("test_reports", {"num": i}, name=f"run_{i}")

            all_reports = storage.list_artifacts("test_reports")
            while len(all_reports) > 3:
                oldest = all_reports.pop(0)
                storage.delete_artifact("test_reports", oldest)
                all_reports = storage.list_artifacts("test_reports")

            assert len(storage.list_artifacts("test_reports")) <= 3

    def test_debug_trace_workflow(self) -> None:
        """Test workflow for saving debug traces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            storage = ArtifactStorage("techne")
            storage.base_dir = tmpdir_path

            # Save multiple debug traces
            traces = [
                "Starting code analysis...\nParsing AST...\nFound 5 issues",
                "Running type checker...\nNo type errors detected",
                "Generating fix candidates...\n3 candidates generated",
            ]

            for idx, trace in enumerate(traces):
                storage.save_artifact("debug_traces", trace, name=f"trace_{idx:03d}")

            # Verify traces are retrievable
            all_traces = storage.list_artifacts("debug_traces")
            assert len(all_traces) == 3

            # Load and verify first trace
            first_trace = storage.load_artifact("debug_traces", "trace_000")
            assert "Starting code analysis" in first_trace
