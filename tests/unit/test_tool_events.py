"""Unit tests for kourai_common.tool_events module (M15).

Verifies JSONL record structure, session contextvar threading, and
args truncation.
"""

from __future__ import annotations

import json
import logging
from contextlib import suppress
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from kourai_common import tool_events
from kourai_common.log import set_session_id

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _isolate_tool_event_logger(tmp_path: Path):
    """Redirect tool-event JSONL to a tmp dir so tests don't pollute repo logs."""
    tool_events._jsonl_logger = None  # force re-init
    with patch.object(tool_events, "_logs_dir", return_value=tmp_path):
        yield
    # Tear down: close and remove any handlers added during the test.
    logger = logging.getLogger("kourai.tool_events")
    for h in logger.handlers[:]:
        with suppress(Exception):
            h.close()
        logger.removeHandler(h)
    tool_events._jsonl_logger = None


@pytest.fixture(autouse=True)
def _reset_session():
    """Ensure session contextvar is clean between tests."""
    set_session_id("")
    yield
    set_session_id("")


class TestLogToolEvent:
    """Core tool-event JSONL record tests."""

    def test_writes_valid_jsonl(self, tmp_path: Path):
        tool_events.log_tool_event("techne", "write_file", {"path": "src/math.py"}, 142, "ok")

        jsonl_file = tmp_path / "tool_events.jsonl"
        assert jsonl_file.exists(), "JSONL file was not created"

        lines = jsonl_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

        record = json.loads(lines[0])
        assert record["agent"] == "techne"
        assert record["tool"] == "write_file"
        assert record["ms"] == 142
        assert record["result"] == "ok"
        assert "ts" in record
        assert "session" in record

    def test_error_result_preserved(self, tmp_path: Path):
        tool_events.log_tool_event(
            "dokimasia", "run_tests", {}, 500, "ERROR: TestFailure: 2 tests failed"
        )

        jsonl_file = tmp_path / "tool_events.jsonl"
        record = json.loads(jsonl_file.read_text(encoding="utf-8").strip())
        assert record["result"].startswith("ERROR")
        assert "TestFailure" in record["result"]

    def test_session_from_contextvar(self, tmp_path: Path):
        set_session_id("946e593a")
        tool_events.log_tool_event("metis", "plan", {}, 100, "ok")

        jsonl_file = tmp_path / "tool_events.jsonl"
        record = json.loads(jsonl_file.read_text(encoding="utf-8").strip())
        assert record["session"] == "946e593a"

    def test_session_empty_when_unset(self, tmp_path: Path):
        tool_events.log_tool_event("puck", "joke", {}, 10, "ok")

        jsonl_file = tmp_path / "tool_events.jsonl"
        record = json.loads(jsonl_file.read_text(encoding="utf-8").strip())
        assert record["session"] == ""


class TestArgsTruncation:
    """Verify args summary respects the 120-char limit."""

    def test_short_args_preserved(self):
        summary = tool_events._summarize_args({"path": "src/math.py"})
        assert summary == "path=src/math.py"
        assert len(summary) <= tool_events._MAX_ARGS_LEN

    def test_long_args_truncated(self):
        long_val = "x" * 200
        summary = tool_events._summarize_args({"content": long_val})
        assert len(summary) <= tool_events._MAX_ARGS_LEN
        assert summary.endswith("...")

    def test_multiple_args_truncated(self):
        args = {f"arg{i}": f"value_{i}" * 10 for i in range(10)}
        summary = tool_events._summarize_args(args)
        assert len(summary) <= tool_events._MAX_ARGS_LEN
