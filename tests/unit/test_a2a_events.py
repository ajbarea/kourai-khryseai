"""Unit tests for ``kourai_common.a2a_events`` part-extraction helpers.

The existing ``extract_parts_text`` is exercised indirectly via downstream
host tests; the new ``extract_parts_data`` / ``extract_artifact_data``
helpers (added for the #17 soft-fail surface) get direct coverage here.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from kourai_common.a2a_events import (
    extract_artifact_data,
    extract_parts_data,
)
from kourai_common.messaging import data_part, text_part


class TestExtractPartsData:
    def test_recovers_dict_from_real_data_part(self):
        part = data_part({"commit_count": 0, "commit_types": []})
        out = extract_parts_data([part])
        assert out == [{"commit_count": 0, "commit_types": []}]

    def test_skips_text_only_parts(self):
        out = extract_parts_data([text_part("hello")])
        assert out == []

    def test_mixed_parts_only_returns_data(self):
        out = extract_parts_data(
            [text_part("intro"), data_part({"commit_count": 2}), text_part("outro")]
        )
        assert out == [{"commit_count": 2}]

    def test_handles_non_iterable(self):
        assert extract_parts_data(42) == []

    def test_empty_list_returns_empty(self):
        assert extract_parts_data([]) == []


class TestExtractArtifactData:
    def test_returns_dicts_from_artifact(self):
        event = MagicMock()
        event.artifact.parts = [data_part({"commit_count": 3})]
        out = extract_artifact_data(event)
        assert out == [{"commit_count": 3}]

    def test_no_artifact_returns_empty(self):
        event = MagicMock()
        event.artifact = None
        assert extract_artifact_data(event) == []
