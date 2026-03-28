"""Agentic artifact storage via HF-Mount buckets.

Agents use this module to persist working outputs (test reports, traces,
debug logs) to HuggingFace Storage Buckets without needing git versioning.

Requires: hf-mount running with agent's bucket mounted at AGENT_ARTIFACTS_DIR env var.

Example:
    from kourai_common.artifacts import ArtifactStorage

    storage = ArtifactStorage("dokimasia")
    report = {"passed": 100, "failed": 5}
    storage.save_artifact("test_reports", report, name="run_001")

"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AGENT_ARTIFACTS_DIR = Path(
    os.getenv("AGENT_ARTIFACTS_DIR") or Path(tempfile.gettempdir()) / "kourai-artifacts"
)


class ArtifactStorage:
    """Manages artifact persistence for agents via HF-Mount.

    Artifacts are automatically synced to HF Storage Buckets when hf-mount
    is running. Without hf-mount, artifacts save to local temporary storage.
    """

    def __init__(self, agent_name: str):
        """Initialize artifact storage for an agent.

        Args:
            agent_name: Name of the agent (e.g., 'dokimasia', 'techne')
        """
        self.agent_name = agent_name
        self.base_dir = AGENT_ARTIFACTS_DIR

        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(
                f"Could not create artifact directory {self.base_dir}: {e}. "
                "Using fallback temporary directory."
            )
            fallback_dir = Path(tempfile.gettempdir()) / "kourai-artifacts-fallback"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            self.base_dir = fallback_dir

    def save_artifact(
        self,
        artifact_type: str,
        content: str | dict | bytes,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Save an artifact to the bucket.

        Args:
            artifact_type: Category (e.g., 'test_reports', 'debug_traces', 'tool_outputs')
            content: Artifact content (str, dict, or bytes)
            name: Optional custom filename (default: auto-generated with timestamp)
            metadata: Optional metadata dict to save alongside artifact

        Returns:
            Path to saved artifact (for logging/reference)

        Example:
            storage = ArtifactStorage("dokimasia")
            report = {"passed": 100, "failed": 5, "duration": 23.4}
            path = storage.save_artifact("test_reports", report, name="run_20260325")

        """

        artifact_dir = self.base_dir / artifact_type
        artifact_dir.mkdir(parents=True, exist_ok=True)

        if name is None:
            timestamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
            name = f"{artifact_type}_{timestamp}"

        data_to_write: str | bytes
        if isinstance(content, dict):
            filename = f"{name}.json"
            data_to_write = json.dumps(content, indent=2, default=str)
        elif isinstance(content, bytes):
            filename = f"{name}.bin"
            data_to_write = content
        else:
            filename = f"{name}.txt"
            data_to_write = str(content)

        artifact_path = artifact_dir / filename
        if isinstance(data_to_write, bytes):
            artifact_path.write_bytes(data_to_write)
        else:
            artifact_path.write_text(data_to_write, encoding="utf-8")

        if metadata:
            metadata_path = artifact_dir / f"{name}.metadata.json"
            metadata_copy = metadata.copy()
            metadata_copy["saved_at"] = datetime.now().isoformat()
            metadata_copy["artifact_type"] = artifact_type
            metadata_copy["agent"] = self.agent_name
            metadata_path.write_text(json.dumps(metadata_copy, indent=2), encoding="utf-8")

        return artifact_path

    def load_artifact(self, artifact_type: str, name: str) -> str | dict | bytes:
        """Load a previously saved artifact.

        Args:
            artifact_type: Category (e.g., 'test_reports')
            name: Artifact name (without extension)

        Returns:
            Artifact content (auto-detected type)

        Raises:
            FileNotFoundError: If artifact doesn't exist
        """
        artifact_dir = self.base_dir / artifact_type

        for suffix in [".json", ".bin", ".txt"]:
            path = artifact_dir / f"{name}{suffix}"
            if path.exists():
                if suffix == ".json":
                    return json.loads(path.read_text(encoding="utf-8"))
                elif suffix == ".bin":
                    return path.read_bytes()
                else:
                    return path.read_text(encoding="utf-8")

        raise FileNotFoundError(f"Artifact not found: {artifact_type}/{name} in {artifact_dir}")

    def list_artifacts(self, artifact_type: str) -> list[str]:
        """List all artifacts of a given type.

        Args:
            artifact_type: Category (e.g., 'test_reports')

        Returns:
            List of artifact names (without extension), sorted chronologically
        """
        artifact_dir = self.base_dir / artifact_type
        if not artifact_dir.exists():
            return []

        names = set()
        for path in artifact_dir.glob("*"):
            if path.suffix == ".metadata":
                continue
            name = path.stem
            names.add(name)

        return sorted(names)

    def delete_artifact(self, artifact_type: str, name: str) -> bool:
        """Delete an artifact and its metadata.

        Args:
            artifact_type: Category
            name: Artifact name (without extension)

        Returns:
            True if deleted, False if not found
        """
        artifact_dir = self.base_dir / artifact_type
        deleted = False

        for path in artifact_dir.glob(f"{name}.*"):
            path.unlink()
            deleted = True

        return deleted

    @property
    def artifacts_path(self) -> Path:
        """Get the mounted artifacts directory."""
        return self.base_dir

    def summary(self) -> dict[str, Any]:
        """Get summary of all artifacts for this agent.

        Returns:
            Dict with artifact counts by type
        """
        types_summary: dict[str, int] = {}

        if self.base_dir.exists():
            for type_dir in self.base_dir.iterdir():
                if type_dir.is_dir():
                    artifact_names = self.list_artifacts(type_dir.name)
                    if artifact_names:
                        types_summary[type_dir.name] = len(artifact_names)

        return {
            "agent": self.agent_name,
            "artifacts_path": str(self.artifacts_path),
            "types": types_summary,
        }
