"""Shared test fixtures for Kourai Khryseai."""

from __future__ import annotations

import pytest


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
