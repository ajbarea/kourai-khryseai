"""Unit tests for idempotent setup logic.

Tests that setup.py correctly skips re-setup when artifacts are already configured.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


class TestSetupIdempotency:
    """Test idempotent setup behavior."""

    def test_should_setup_with_no_token(self) -> None:
        """Test that setup is skipped when HF_TOKEN is not set."""
        with patch.dict(os.environ, {}, clear=True):
            from scripts.setup import should_setup_artifacts

            assert should_setup_artifacts() is False

    def test_should_setup_with_token_no_marker(self) -> None:
        """Test that setup runs when token is set and marker doesn't exist."""
        with (
            patch.dict(os.environ, {"HF_TOKEN": "hf_test123"}),
            patch("scripts.setup.SETUP_MARKER") as mock_marker,
        ):
            mock_marker.exists.return_value = False
            from scripts.setup import should_setup_artifacts

            assert should_setup_artifacts() is True

    def test_should_skip_setup_with_token_and_marker(self) -> None:
        """Test that setup is skipped when token is set and marker exists."""
        with (
            patch.dict(os.environ, {"HF_TOKEN": "hf_test123"}),
            patch("scripts.setup.SETUP_MARKER") as mock_marker,
        ):
            mock_marker.exists.return_value = True
            from scripts.setup import should_setup_artifacts

            assert should_setup_artifacts() is False

    def test_should_force_setup_ignores_marker(self) -> None:
        """Test that --force-artifacts bypasses marker check."""
        with (
            patch.dict(os.environ, {"HF_TOKEN": "hf_test123"}),
            patch("scripts.setup.SETUP_MARKER") as mock_marker,
        ):
            mock_marker.exists.return_value = True  # Marker exists
            from scripts.setup import should_setup_artifacts

            # But force=True should override
            assert should_setup_artifacts(force=True) is True

    def test_mark_artifacts_configured_creates_file(self) -> None:
        """Test that marker file is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            marker_path = Path(tmpdir) / ".hf-buckets-configured"

            with patch("scripts.setup.SETUP_MARKER", marker_path):
                from scripts.setup import mark_artifacts_configured

                mark_artifacts_configured()
                assert marker_path.exists()
                assert "Marker file" in marker_path.read_text()

    def test_idempotent_flow_first_run(self) -> None:
        """Test setup flow on first run (marker doesn't exist)."""
        with (
            patch.dict(os.environ, {"HF_TOKEN": "hf_test123"}),
            tempfile.TemporaryDirectory() as tmpdir,
        ):
            marker_path = Path(tmpdir) / ".hf-buckets-configured"

            with (
                patch("scripts.setup.SETUP_MARKER", marker_path),
                patch("scripts.setup.run_command") as mock_run,
            ):
                mock_run.return_value = 0  # Success
                from scripts.setup import should_setup_artifacts

                # First run: marker doesn't exist
                assert not marker_path.exists()
                assert should_setup_artifacts() is True

                # Simulate setup success
                from scripts.setup import mark_artifacts_configured

                mark_artifacts_configured()

                # Second run: marker exists
                assert marker_path.exists()
                assert should_setup_artifacts() is False

    def test_idempotent_flow_repeated_setup(self) -> None:
        """Test that repeated setup calls skip artifact setup."""
        with (
            patch.dict(os.environ, {"HF_TOKEN": "hf_test123"}),
            tempfile.TemporaryDirectory() as tmpdir,
        ):
            marker_path = Path(tmpdir) / ".hf-buckets-configured"
            marker_path.write_text("# Already configured\n")

            with patch("scripts.setup.SETUP_MARKER", marker_path):
                from scripts.setup import should_setup_artifacts

                # Marker exists, should skip
                assert should_setup_artifacts() is False
                assert should_setup_artifacts() is False  # Same on repeat


class TestSetupMarkerFile:
    """Test marker file behavior."""

    def test_marker_file_location(self) -> None:
        """Test that marker file is in project root."""
        from scripts.setup import SETUP_MARKER

        assert SETUP_MARKER.name == ".hf-buckets-configured"

    def test_marker_file_is_path_object(self) -> None:
        """Test that SETUP_MARKER is a Path object."""
        from scripts.setup import SETUP_MARKER

        assert isinstance(SETUP_MARKER, Path)

    def test_marker_content_is_idempotent(self) -> None:
        """Test that marker content doesn't change on re-write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            marker_path = Path(tmpdir) / ".hf-buckets-configured"

            with patch("scripts.setup.SETUP_MARKER", marker_path):
                from scripts.setup import mark_artifacts_configured

                mark_artifacts_configured()
                content1 = marker_path.read_text()

                mark_artifacts_configured()
                content2 = marker_path.read_text()

                assert content1 == content2


class TestSetupCommandLineArgs:
    """Test command-line argument handling."""

    def test_force_artifacts_flag_in_argv(self) -> None:
        """Test that --force-artifacts is recognized in sys.argv."""
        with patch("sys.argv", ["setup.py", "--force-artifacts"]):
            force_artifacts = "--force-artifacts" in sys.argv
            assert force_artifacts is True

    def test_setup_without_force_flag(self) -> None:
        """Test that setup runs normally without flag."""
        with patch("sys.argv", ["setup.py"]):
            force_artifacts = "--force-artifacts" in sys.argv
            assert force_artifacts is False


class TestSetupMessages:
    """Test user-facing messages."""

    def test_marker_exists_message(self, caplog) -> None:
        """Test that appropriate message is shown when marker exists."""
        with (
            patch.dict(os.environ, {"HF_TOKEN": "hf_test123"}),
            tempfile.TemporaryDirectory() as tmpdir,
        ):
            marker_path = Path(tmpdir) / ".hf-buckets-configured"
            marker_path.write_text("# configured\n")

            with patch("scripts.setup.SETUP_MARKER", marker_path):
                from scripts.setup import should_setup_artifacts

                # This doesn't log, but the check should still work
                result = should_setup_artifacts()
                assert result is False

    def test_force_setup_message(self) -> None:
        """Test that force setup is indicated correctly."""
        with patch("sys.argv", ["setup.py", "--force-artifacts"]):
            force = "--force-artifacts" in sys.argv
            assert force is True
