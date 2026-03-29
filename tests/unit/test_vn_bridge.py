"""Tests for the Ren'Py VN bridge (hosts/vn/kourai_vn/game/libs/bridge.py).

Focuses on the RenPyBridge class, which manages HTTP communication with the
vn-bridge Docker service. Covers service lifecycle, messaging, TTS, and gossip.
"""

from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# bridge.py is not an installable package — add its directory to the path
_LIBS_DIR = Path(__file__).parents[2] / "hosts/vn/kourai_vn/game/libs"
if str(_LIBS_DIR) not in sys.path:
    sys.path.insert(0, str(_LIBS_DIR))

from bridge import RenPyBridge, _find_project_root  # type: ignore[import-not-found]

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def bridge(tmp_path: Path) -> RenPyBridge:
    """RenPyBridge with its project root and game dir redirected to a temp directory.

    Prevents log file and TTS audio file creation in the real project tree during tests.
    """
    with patch("bridge._find_project_root", return_value=tmp_path):
        b = RenPyBridge(agent_script="agents/vn_bridge.py")
    b.game_dir = tmp_path / "game"
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

    def test_inbox_is_empty(self, bridge: RenPyBridge) -> None:
        assert bridge.inbox.empty()

    def test_errors_is_empty(self, bridge: RenPyBridge) -> None:
        assert bridge.errors.empty()

    def test_log_dir_created(self, bridge: RenPyBridge) -> None:
        """__init__ must create the logs/ directory immediately."""
        assert bridge.log_dir.exists()


def _ok_response() -> MagicMock:
    """Mock urlopen response returning {"status": "ok"}."""
    resp = MagicMock()
    resp.read.return_value = b'{"status": "ok"}'
    return resp


# ── RenPyBridge — start ───────────────────────────────────────────────────────


class TestStart:
    def test_returns_false_when_docker_unreachable(self, bridge: RenPyBridge) -> None:
        """Docker service unreachable → start() returns False without raising."""
        url_err = urllib.error.URLError(reason="Connection refused")
        # time.time side_effect: [deadline_calc=0, while_check=0, while_check=11]
        with (
            patch("urllib.request.urlopen", side_effect=url_err),
            patch("time.sleep"),
            patch("time.time", side_effect=[0, 0, 11]),
        ):
            result = bridge.start()
        assert result is False
        assert bridge.is_running is False

    def test_queues_error_when_docker_unreachable(self, bridge: RenPyBridge) -> None:
        """Start failure queues a user-visible error mentioning the Docker service."""
        url_err = urllib.error.URLError(reason="Connection refused")
        with (
            patch("urllib.request.urlopen", side_effect=url_err),
            patch("time.sleep"),
            patch("time.time", side_effect=[0, 0, 11]),
        ):
            bridge.start()
        err = bridge.get_error()
        assert err is not None
        assert "docker" in err.lower() or "vn-bridge" in err.lower()

    def test_returns_false_when_service_unhealthy(self, bridge: RenPyBridge) -> None:
        """Service returns status=disconnected → start() returns False."""
        resp = MagicMock()
        resp.read.return_value = b'{"status": "disconnected"}'
        with (
            patch("urllib.request.urlopen", return_value=resp),
            patch("time.sleep"),
            patch("time.time", side_effect=[0, 0, 11]),
        ):
            result = bridge.start()
        assert result is False
        assert bridge.is_running is False

    def test_returns_true_and_sets_running_on_success(self, bridge: RenPyBridge) -> None:
        """Healthy Docker service → start() returns True and sets is_running=True."""
        with (
            patch("urllib.request.urlopen", return_value=_ok_response()),
            patch("time.sleep"),
        ):
            result = bridge.start()
        assert result is True
        assert bridge.is_running is True


# ── RenPyBridge — send_message ────────────────────────────────────────────────


class TestSendMessage:
    def test_returns_false_when_not_running(self, bridge: RenPyBridge) -> None:
        assert bridge.send_message({"action": "message", "text": "hello"}) is False

    def test_routes_message_action_to_streaming(self, bridge: RenPyBridge) -> None:
        """'message' action spawns a thread targeting _post_streaming."""
        bridge.is_running = True
        mock_thread = MagicMock()
        with patch("bridge.threading.Thread", return_value=mock_thread) as thread_cls:
            result = bridge.send_message({"action": "message", "text": "hello forge"})
        assert result is True
        mock_thread.start.assert_called_once()
        _, kwargs = thread_cls.call_args
        assert kwargs["target"].__name__ == "_post_streaming"

    def test_routes_non_message_action_to_action_post(self, bridge: RenPyBridge) -> None:
        """Non-message actions (e.g. get_profiles) route to _post_action."""
        bridge.is_running = True
        mock_thread = MagicMock()
        with patch("bridge.threading.Thread", return_value=mock_thread) as thread_cls:
            result = bridge.send_message({"action": "get_profiles"})
        assert result is True
        mock_thread.start.assert_called_once()
        _, kwargs = thread_cls.call_args
        assert kwargs["target"].__name__ == "_post_action"

    def test_streaming_error_queues_error_string(self, bridge: RenPyBridge) -> None:
        """HTTP failure in _post_streaming puts an error string into the error queue."""
        bridge.is_running = True
        with patch("urllib.request.urlopen", side_effect=OSError("connection reset")):
            bridge._post_streaming({"action": "message", "text": "test"})
        err = bridge.get_error()
        assert err is not None
        assert "connection reset" in err.lower() or "streaming" in err.lower()


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

    def test_shutdown_writes_log_entry(self, bridge: RenPyBridge) -> None:
        """shutdown() writes a log entry so operators can see clean teardown."""
        bridge.is_running = True
        bridge.shutdown()
        log_content = bridge.log_file.read_text(encoding="utf-8")
        assert "shutdown" in log_content.lower()

    def test_shutdown_is_safe_when_not_started(self, bridge: RenPyBridge) -> None:
        """shutdown() must not raise even if start() was never called."""
        bridge.shutdown()  # should not raise
        assert bridge.is_running is False


# ── RenPyBridge — request_tts ────────────────────────────────────────────────


def _audio_response(data: bytes = b"\xff\xfb\x90\x00" * 100) -> MagicMock:
    """Mock urlopen response returning MP3-like audio bytes."""
    resp = MagicMock()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.status = 200
    resp.read.return_value = data
    return resp


def _json_response(data: dict, status: int = 200) -> MagicMock:
    """Mock urlopen response returning JSON."""
    resp = MagicMock()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.status = status
    resp.read.return_value = json.dumps(data).encode()
    return resp


class TestRequestTts:
    def test_returns_renpy_relative_path_on_success(
        self, bridge: RenPyBridge, tmp_path: Path
    ) -> None:
        """Successful TTS returns a Ren'Py-relative path like 'audio/tts/tts_techne.mp3'."""
        with patch("urllib.request.urlopen", return_value=_audio_response()):
            result = bridge.request_tts("Hello world.", "techne")
        assert result == "audio/tts/tts_techne.mp3"

    def test_writes_mp3_file_to_disk(self, bridge: RenPyBridge) -> None:
        """TTS audio bytes are written to game/audio/tts/ directory."""
        audio_bytes = b"\xff\xfb\x90\x00" * 50
        with patch("urllib.request.urlopen", return_value=_audio_response(audio_bytes)):
            bridge.request_tts("Test audio.", "kallos")
        tts_file = bridge.game_dir / "audio" / "tts" / "tts_kallos.mp3"
        assert tts_file.read_bytes() == audio_bytes

    def test_returns_none_on_http_error(self, bridge: RenPyBridge) -> None:
        """HTTP failure returns None, not an exception."""
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            result = bridge.request_tts("Hello.", "metis")
        assert result is None

    def test_returns_none_on_empty_response(self, bridge: RenPyBridge) -> None:
        """Empty audio response returns None."""
        with patch("urllib.request.urlopen", return_value=_audio_response(b"")):
            result = bridge.request_tts("Hello.", "techne")
        assert result is None

    def test_returns_none_on_non_200_status(self, bridge: RenPyBridge) -> None:
        """Non-200 HTTP status returns None."""
        resp = _audio_response()
        resp.status = 500
        with patch("urllib.request.urlopen", return_value=resp):
            result = bridge.request_tts("Hello.", "techne")
        assert result is None


# ── RenPyBridge — request_gossip ─────────────────────────────────────────────


class TestRequestGossip:
    def test_returns_tuple_on_success(self, bridge: RenPyBridge) -> None:
        """Successful gossip returns (hint, line) tuple."""
        gossip_data = {"hint": "*glancing over*", "line": "They're improving."}
        with patch("urllib.request.urlopen", return_value=_json_response(gossip_data)):
            result = bridge.request_gossip("techne", "player-123", {"techne": 0.6})
        assert result == ("*glancing over*", "They're improving.")

    def test_returns_none_on_http_error(self, bridge: RenPyBridge) -> None:
        """Network failure returns None for fallback to static lines."""
        with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            result = bridge.request_gossip("kallos", "player-123", {})
        assert result is None

    def test_returns_none_on_non_200_status(self, bridge: RenPyBridge) -> None:
        """Non-200 HTTP status returns None."""
        resp = _json_response({"error": "unknown agent"}, status=400)
        with patch("urllib.request.urlopen", return_value=resp):
            result = bridge.request_gossip("unknown", "player-123", {})
        assert result is None

    def test_returns_none_on_empty_line(self, bridge: RenPyBridge) -> None:
        """Empty gossip line returns None."""
        gossip_data = {"hint": "*observing*", "line": ""}
        with patch("urllib.request.urlopen", return_value=_json_response(gossip_data)):
            result = bridge.request_gossip("metis", "player-123", {})
        assert result is None

    def test_defaults_hint_when_missing(self, bridge: RenPyBridge) -> None:
        """Missing 'hint' key defaults to '*observing*'."""
        gossip_data = {"line": "Interesting patterns forming."}
        with patch("urllib.request.urlopen", return_value=_json_response(gossip_data)):
            result = bridge.request_gossip("metis", "player-123", {})
        assert result is not None
        assert result[0] == "*observing*"
        assert result[1] == "Interesting patterns forming."

    def test_passes_affinity_in_request_body(self, bridge: RenPyBridge) -> None:
        """Affinity data is included in the POST body."""
        gossip_data = {"hint": "*thinking*", "line": "They work hard."}
        affinity = {"techne": 0.7, "kallos": 0.3}
        with patch("urllib.request.urlopen", return_value=_json_response(gossip_data)) as mock_open:
            bridge.request_gossip("techne", "player-123", affinity)
        # Extract the body from the Request object
        call_args = mock_open.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        assert body["agent"] == "techne"
        assert body["player_id"] == "player-123"
        assert body["affinity"] == affinity
