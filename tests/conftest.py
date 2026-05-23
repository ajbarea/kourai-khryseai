"""Shared test fixtures for Kourai Khryseai."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from a2a.types import Message, Task, TaskArtifactUpdateEvent, TaskStatusUpdateEvent


@pytest.fixture
def isolated_player_stores(tmp_path, monkeypatch):
    """Redirect PlayerProfile + CLISettings persistence to per-test tmp paths.

    Tests that touch player identity / mode preferences need both stores
    isolated from the live install:
    - PlayerProfile persists under `~/.kourai_khryseai/profiles/<id>.json`
    - CLISettings persists at `<repo>/.cache/cli_settings.json`

    Mirrors the heavier `test_onboarding_hooks._isolate_db` pattern but
    skips the sqlite memory DB setup (this fixture is for tests that
    only need the JSON-on-disk halves of the player infra).

    Yields ``(active_profile_file, settings_path)`` so individual tests
    can read the raw on-disk state when an assertion needs byte-level
    inspection.
    """
    import kourai_common.player as player_mod

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    active_profile_file = tmp_path / "active_profile.txt"
    settings_path = tmp_path / "cli_settings.json"

    monkeypatch.setattr(player_mod, "PLAYER_DIR", tmp_path)
    monkeypatch.setattr(player_mod, "PROFILES_DIR", profiles_dir)
    monkeypatch.setattr(player_mod, "ACTIVE_PROFILE_FILE", active_profile_file)
    monkeypatch.setattr(player_mod, "_LEGACY_PLAYER_FILE", tmp_path / "player.json")
    if hasattr(player_mod, "_profile_cache"):
        player_mod._profile_cache = None
    if hasattr(player_mod, "_profile_cache_ts"):
        player_mod._profile_cache_ts = 0.0
    monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", settings_path)

    yield active_profile_file, settings_path


@pytest.fixture
def agent_ports() -> dict[str, int]:
    """Port assignments for all agents."""
    return {
        "hephaestus": 10000,
        "metis": 10001,
        "techne": 10002,
        "dokimasia": 10003,
        "kallos": 10004,
        "mneme": 10005,
    }


def make_stream_response(event: object) -> MagicMock:
    """Wrap an event in a StreamResponse-shaped mock for v1.0 ``client.send_message`` tests.

    Production consumes ``client.send_message`` yields via
    ``kourai_common.messaging.stream_event(response)``, which calls
    ``response.HasField("message" | "task" | "status_update" |
    "artifact_update")`` to discriminate the inner event. Test mocks that
    yielded raw ``Message`` / ``(task, update)`` tuples (the v0.3 yield
    shape) trip ``stream_event`` because tuples have no ``HasField``.

    This helper accepts any of the four inner event types — including
    ``MagicMock(spec=Type)`` instances, which ``isinstance`` recognizes —
    and returns a ``StreamResponse``-like mock with both the field
    attribute and ``HasField(name)`` wired so ``stream_event`` decodes it
    correctly.
    """
    sr = MagicMock()
    is_message = isinstance(event, Message)
    is_task = isinstance(event, Task)
    is_status = isinstance(event, TaskStatusUpdateEvent)
    is_artifact = isinstance(event, TaskArtifactUpdateEvent)

    def has_field(name: str) -> bool:
        if name == "message":
            return is_message
        if name == "task":
            return is_task
        if name == "status_update":
            return is_status
        if name == "artifact_update":
            return is_artifact
        return False

    sr.HasField = has_field
    if is_message:
        sr.message = event
    if is_task:
        sr.task = event
    if is_status:
        sr.status_update = event
    if is_artifact:
        sr.artifact_update = event
    return sr


@pytest.fixture(scope="module")
def vcr_config() -> dict[str, object]:
    """vcrpy / pytest-recording cassette config -- scrub auth headers."""
    import pathlib

    return {
        "filter_headers": [
            ("authorization", "REDACTED"),
            ("api-key", "REDACTED"),
            ("x-api-key", "REDACTED"),
        ],
        # record_mode intentionally absent -- CLI --record-mode flag controls
        # it; addopts in pyproject.toml sets the default of "none" for CI.
        # Single cassette store for all integration tests.
        "cassette_library_dir": str(pathlib.Path(__file__).parent / "cassettes"),
    }
