"""Agentic artifact storage with HuggingFace Bucket sync.

Agents use this module to persist working outputs (test reports, traces,
debug logs) to HuggingFace Storage Buckets.

Local writes are always fast and synchronous. Cloud sync is explicit:
call pull() at agent startup to restore prior state from HF, and push()
after task completion to persist artifacts to the bucket.

Without HF_TOKEN the module operates in local-only mode without error —
useful for development and testing.

Example:
    from kourai_common.artifacts import ArtifactStorage

    storage = ArtifactStorage("dokimasia")
    storage.pull()                                    # restore from HF on startup

    report = {"passed": 100, "failed": 5}
    storage.save_artifact("test_reports", report, name="run_001")
    storage.push()                                    # sync to HF after task

Bucket layout on HF:
    hf://buckets/<user>/kourai-artifacts/<agent_name>/<artifact_type>/<filename>
    e.g. hf://buckets/jdoe/kourai-artifacts/dokimasia/test_reports/run_001.json

"""

from __future__ import annotations

import contextlib
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
_DEFAULT_BUCKET_SUFFIX = "kourai-artifacts"
_cached_bucket_id: str | None = None
_bucket_id_resolved = False


def _resolve_bucket_id() -> str | None:
    """Derive the HF bucket ID from KOURAI_BUCKET_ID or the authenticated user.

    Result is cached per-process so the HF API is called at most once,
    not once per agent.
    """
    global _cached_bucket_id, _bucket_id_resolved

    explicit = os.getenv("KOURAI_BUCKET_ID")
    if explicit:
        return explicit

    if _bucket_id_resolved:
        return _cached_bucket_id

    try:
        from huggingface_hub import HfApi  # type: ignore[import-untyped]

        username = HfApi().whoami()["name"]
        _cached_bucket_id = f"{username}/{_DEFAULT_BUCKET_SUFFIX}"
        logger.info("KOURAI_BUCKET_ID not set — using %s", _cached_bucket_id)
    except Exception as e:
        logger.debug("Could not resolve HF username for bucket ID: %s", e)
        _cached_bucket_id = None
    finally:
        _bucket_id_resolved = True

    return _cached_bucket_id


class ArtifactStorage:
    """Manages artifact persistence for agents with HuggingFace Bucket sync.

    Local writes are always synchronous and fast. Cloud sync is explicit via
    push() / pull(). If HF_TOKEN is not set, operates in local-only mode.
    """

    def __init__(self, agent_name: str):
        """Initialize artifact storage for an agent.

        Args:
            agent_name: Name of the agent (e.g., 'dokimasia', 'techne')
        """
        self.agent_name = agent_name
        self.base_dir = Path(os.getenv("AGENT_ARTIFACTS_DIR") or AGENT_ARTIFACTS_DIR)
        self.hf_enabled = bool(os.getenv("HF_TOKEN"))

        if self.hf_enabled:
            self._bucket_id = _resolve_bucket_id()
            if not self._bucket_id:
                logger.warning(
                    "HF_TOKEN is set but bucket ID could not be resolved — disabling HF sync"
                )
                self.hf_enabled = False
        else:
            self._bucket_id = None
            logger.debug("HF_TOKEN not set — artifact storage in local-only mode")

        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(
                f"Could not create artifact directory {self.base_dir}: {e}. "
                "Using fallback temporary directory."
            )
            fallback_dir = Path(tempfile.gettempdir()) / "kourai-artifacts-fallback"
            with contextlib.suppress(OSError):
                fallback_dir.mkdir(parents=True, exist_ok=True)
            self.base_dir = fallback_dir

    @property
    def hf_path(self) -> str:
        """Remote HF bucket path for this agent's artifacts."""
        return f"hf://buckets/{self._bucket_id}/{self.agent_name}"

    def push(self) -> bool:
        """Sync local artifacts to HuggingFace bucket.

        Uses rsync-style transfer — only changed files are uploaded.
        Blocking network call; run at task completion, not in hot paths.
        No-op (returns True) if HF_TOKEN is not set.

        Returns:
            True if sync succeeded or skipped, False on error.
        """
        if not self.hf_enabled:
            logger.debug("push() skipped — HF_TOKEN not set")
            return True
        try:
            from huggingface_hub import sync_bucket  # type: ignore[import-untyped]

            sync_bucket(str(self.base_dir), self.hf_path, quiet=True)
            logger.info("Artifacts pushed → %s", self.hf_path)
            return True
        except Exception as e:
            logger.warning("Failed to push artifacts to HF bucket: %s", e)
            return False

    def pull(self) -> bool:
        """Sync artifacts from HuggingFace bucket to local storage.

        Uses rsync-style transfer — only changed files are downloaded.
        Blocking network call; run at agent startup, not in hot paths.
        No-op (returns True) if HF_TOKEN is not set. Non-fatal if the
        remote path does not exist yet (first run).

        Returns:
            True if sync succeeded or skipped, False on hard error.
        """
        if not self.hf_enabled:
            logger.debug("pull() skipped — HF_TOKEN not set")
            return True
        try:
            from huggingface_hub import sync_bucket  # type: ignore[import-untyped]

            sync_bucket(self.hf_path, str(self.base_dir), quiet=True)
            logger.info("Artifacts pulled ← %s", self.hf_path)
            return True
        except Exception as e:
            # Remote path may not exist on first run — treat as non-fatal.
            logger.debug("pull() non-fatal (expected on first run): %s", e)
            return False

    def save_artifact(
        self,
        artifact_type: str,
        content: str | dict | bytes,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Save an artifact to local storage.

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
            if ".metadata" in path.suffixes:
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
        """Get the local artifacts directory."""
        return self.base_dir

    def summary(self) -> dict[str, Any]:
        """Get summary of all artifacts for this agent.

        Returns:
            Dict with artifact counts by type and HF sync status
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
            "hf_enabled": self.hf_enabled,
            "hf_bucket": self.hf_path if self.hf_enabled else None,
            "types": types_summary,
        }
