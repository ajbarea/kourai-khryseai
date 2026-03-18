"""Tests for the Ren'Py VN bridge (hosts/vn/kourai_vn/game/libs/bridge.py).

Focuses on the RenPyBridge class, which manages the subprocess and communication.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# bridge.py is not an installable package — add its directory to the path
_LIBS_DIR = Path(__file__).parents[2] / "hosts/vn/kourai_vn/game/libs"
if str(_LIBS_DIR) not in sys.path:
    sys.path.insert(0, str(_LIBS_DIR))

from bridge import RenPyBridge, _find_project_root  # noqa: E402

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def bridge(tmp_path: Path) -> RenPyBridge:
    """RenPyBridge with its project root redirected to a temp directory.

    Prevents log file creation in the real project tree during tests.
    """
    with patch("bridge._find_project_root", return_value=tmp_path):
        b = RenPyBridge(agent_script="agents/vn_bridge.py")
    return b


# ── _find_project_root ────────────────────────────────────────────────────────


class TestFindProjectRoot:
    def test_finds_real_pyproject_toml(self) -> None:
        """Walking up from bridge.py should reach the repo root containing pyproject.toml."""
        root = _find_project_root()
        assert (root / "pyproject.toml").exists()

    def test_falls_back_to_parents_4_when_no_marker(self, tmp_path: Path) -> None:
        """When no pyproject.toml exists in any parent, returns 4 levels up from __file__."""
        fake_file = tmp_path / "a" / "b" / "c" / "d" / "e" / "bridge.py"
        fake_file.parent.mkdir(parents=True)
        fake_file.touch()

        with patch("bridge.__file__", str(fake_file)):
            result = _find_project_root()

        assert result == fake_file.resolve().parents[4]


# ── RenPyBridge — Initialization ─────────────────────────────────────────────


class TestRenPyBridgeInit:
    def test_starts_not_running(self, bridge: RenPyBridge) -> None:
        assert bridge.is_running is False

    def test_process_is_none_before_start(self, bridge: RenPyBridge) -> None:
        assert bridge.process is None

    def test_inbox_is_empty(self, bridge: RenPyBridge) -> None:
        assert bridge.inbox.empty()

    def test_errors_is_empty(self, bridge: RenPyBridge) -> None:
        assert bridge.errors.empty()

    def test_log_dir_created(self, bridge: RenPyBridge) -> None:
        """__init__ must create the logs/ directory immediately."""
        assert bridge.log_dir.exists()


# ── RenPyBridge — check_connection ───────────────────────────────────────────


class TestCheckConnection:
    def test_returns_none_on_200(self, bridge: RenPyBridge) -> None:
        """Successful HTTP response → no error."""
        mock_response = MagicMock()
        with patch("urllib.request.urlopen", return_value=mock_response):
            result = bridge.check_connection(timeout=5.0)
        assert result is None

    def test_pings_hephaestus_port_10000(self, bridge: RenPyBridge) -> None:
        """Always pings Hephaestus on port 10000 (matches AGENT_PORTS)."""
        mock_response = MagicMock()
        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            bridge.check_connection(timeout=5.0)
        called_url = mock_open.call_args[0][0]
        assert "10000" in called_url
        assert "127.0.0.1" in called_url

    def test_returns_error_string_on_http_error(self, bridge: RenPyBridge) -> None:
        """HTTPError (e.g. 503) → descriptive error string, not None."""
        http_err = urllib.error.HTTPError(
            url="http://127.0.0.1:10000/.well-known/agent.json",
            code=503,
            msg="Service Unavailable",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,  # type: ignore[arg-type]
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            result = bridge.check_connection(timeout=5.0)
        assert result is not None
        assert "503" in result

    def test_returns_error_string_on_url_error(self, bridge: RenPyBridge) -> None:
        """URLError (agents not running) → descriptive error string."""
        url_err = urllib.error.URLError(reason="Connection refused")
        with patch("urllib.request.urlopen", side_effect=url_err):
            result = bridge.check_connection(timeout=5.0)
        assert result is not None
        assert "127.0.0.1" in result

    def test_returns_error_string_on_unexpected_exception(self, bridge: RenPyBridge) -> None:
        """Any other exception → descriptive error string, never raises."""
        with patch("urllib.request.urlopen", side_effect=RuntimeError("boom")):
            result = bridge.check_connection(timeout=5.0)
        assert result is not None
        assert "boom" in result

    def test_error_is_logged(self, bridge: RenPyBridge) -> None:
        """Connection failures are written to the log file."""
        url_err = urllib.error.URLError(reason="Connection refused")
        with patch("urllib.request.urlopen", side_effect=url_err):
            bridge.check_connection(timeout=5.0)
        log_content = bridge.log_file.read_text(encoding="utf-8")
        assert "Connection check failed" in log_content


# ── RenPyBridge — start ───────────────────────────────────────────────────────


class TestStart:
    def test_returns_false_when_uv_not_found(self, bridge: RenPyBridge) -> None:
        """No uv on PATH → start() returns False without spawning a process."""
        with patch("shutil.which", return_value=None):
            result = bridge.start()
        assert result is False
        assert bridge.process is None

    def test_queues_error_when_uv_not_found(self, bridge: RenPyBridge) -> None:
        with patch("shutil.which", return_value=None):
            bridge.start()
        err = bridge.get_error()
        assert err is not None
        assert "uv" in err.lower()

    def test_returns_false_when_process_dies_immediately(self, bridge: RenPyBridge) -> None:
        """Process exits before the 1.5s startup window → start() returns False."""
        dead_process = Mock()
        dead_process.poll.return_value = 1  # non-None → dead
        dead_process.stderr.read.return_value = "ImportError: no module named x"

        with (
            patch("shutil.which", return_value="/usr/bin/uv"),
            patch("subprocess.Popen", return_value=dead_process),
            patch("time.sleep"),  # don't actually wait
        ):
            result = bridge.start()

        assert result is False
        assert bridge.is_running is False

    def test_returns_true_and_sets_running_on_success(self, bridge: RenPyBridge) -> None:
        """Healthy process → start() returns True, is_running=True, threads spawned."""
        live_process = Mock()
        live_process.poll.return_value = None  # still alive
        live_process.stdout = MagicMock()
        live_process.stderr = MagicMock()

        with (
            patch("shutil.which", return_value="/usr/bin/uv"),
            patch("subprocess.Popen", return_value=live_process),
            patch("time.sleep"),
            patch.object(bridge, "_read_loop"),  # don't actually start threads
            patch.object(bridge, "_error_loop"),
        ):
            result = bridge.start()

        assert result is True
        assert bridge.is_running is True
        assert bridge.process is live_process


# ── RenPyBridge — send_message ────────────────────────────────────────────────


class TestSendMessage:
    def test_returns_false_when_not_running(self, bridge: RenPyBridge) -> None:
        assert bridge.send_message({"action": "message", "text": "hello"}) is False

    def test_returns_false_when_process_is_none(self, bridge: RenPyBridge) -> None:
        bridge.is_running = True
        bridge.process = None
        assert bridge.send_message({"action": "message", "text": "hello"}) is False

    def test_writes_json_newline_to_stdin(self, bridge: RenPyBridge) -> None:
        """Messages must be JSON lines (newline-terminated) for the reader loop."""
        fake_stdin = MagicMock()
        fake_process = Mock()
        fake_process.stdin = fake_stdin

        bridge.is_running = True
        bridge.process = fake_process

        msg = {"action": "message", "text": "hello forge"}
        result = bridge.send_message(msg)

        assert result is True
        written = fake_stdin.write.call_args[0][0]
        assert written.endswith("\n")
        parsed = json.loads(written.strip())
        assert parsed == msg

    def test_returns_false_and_logs_on_broken_pipe(self, bridge: RenPyBridge) -> None:
        """BrokenPipeError from stdin.write → returns False, does not raise."""
        fake_stdin = MagicMock()
        fake_stdin.write.side_effect = BrokenPipeError("broken pipe")
        fake_process = Mock()
        fake_process.stdin = fake_stdin

        bridge.is_running = True
        bridge.process = fake_process

        result = bridge.send_message({"action": "message", "text": "test"})
        assert result is False


# ── RenPyBridge — get_message / get_error ────────────────────────────────────


class TestQueues:
    def test_get_message_returns_none_when_empty(self, bridge: RenPyBridge) -> None:
        assert bridge.get_message(timeout=0.01) is None

    def test_get_message_returns_queued_item(self, bridge: RenPyBridge) -> None:
        msg = {"agent": "hephaestus", "message": "The forge awakens."}
        bridge.inbox.put(msg)
        result = bridge.get_message(timeout=0.1)
        assert result == msg

    def test_get_error_returns_none_when_empty(self, bridge: RenPyBridge) -> None:
        assert bridge.get_error() is None

    def test_get_error_returns_queued_error(self, bridge: RenPyBridge) -> None:
        bridge.errors.put("uv not found on PATH")
        result = bridge.get_error()
        assert result == "uv not found on PATH"

    def test_get_message_is_fifo(self, bridge: RenPyBridge) -> None:
        """Messages must be delivered in order — important for multi-turn dialogue."""
        msgs = [{"agent": "hephaestus", "message": str(i)} for i in range(5)]
        for m in msgs:
            bridge.inbox.put(m)
        received = [bridge.get_message(timeout=0.1) for _ in msgs]
        assert received == msgs


# ── RenPyBridge — shutdown ───────────────────────────────────────────────────


class TestShutdown:
    def test_sets_is_running_false(self, bridge: RenPyBridge) -> None:
        bridge.is_running = True
        bridge.shutdown()
        assert bridge.is_running is False

    def test_terminates_process(self, bridge: RenPyBridge) -> None:
        mock_process = Mock()
        bridge.process = mock_process
        bridge.is_running = True
        bridge.shutdown()
        mock_process.terminate.assert_called_once()

    def test_shutdown_is_safe_with_no_process(self, bridge: RenPyBridge) -> None:
        """shutdown() must not raise even if process was never started."""
        bridge.process = None
        bridge.shutdown()  # should not raise
        assert bridge.is_running is False
