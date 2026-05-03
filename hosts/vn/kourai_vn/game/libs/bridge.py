"""Bridge between Ren'Py frontend and the vn-bridge Docker service.

Instead of spawning a subprocess, connects to the vn-bridge HTTP server
running in Docker. Same send_message / get_message / is_running API —
no changes needed in script.rpy.
"""

import datetime
import json
import queue
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

BRIDGE_URL = "http://localhost:10010"
_MESSAGE_TIMEOUT = 600.0
_ACTION_TIMEOUT = 30.0
_HEALTH_TIMEOUT = 2.0
_START_DEADLINE = 10.0


def _find_project_root() -> Path:
    """Walk parents from this file until we find pyproject.toml."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path(__file__).resolve().parents[4]


class RenPyBridge:
    """HTTP client bridge to the vn-bridge Docker service.

    Preserves the exact send_message / get_message / is_running API so
    script.rpy needs no changes.
    """

    def __init__(self, agent_script: str = "agents/vn_bridge"):
        # agent_script kept for Ren'Py save/load pickle compatibility only
        self.agent_script = agent_script
        self.is_running = False
        self.inbox: queue.Queue = queue.Queue(maxsize=500)
        self.errors: queue.Queue = queue.Queue()

        self.project_root = _find_project_root()
        self.log_dir = self.project_root / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "bridge_renpy.log"
        self.game_dir: Path = Path(__file__).resolve().parent.parent

    # ── Logging ───────────────────────────────────────────────────────────

    def _log(self, message: str) -> None:
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with Path(self.log_file).open("a", encoding="utf-8") as f:
                f.write(f"[{ts}] {message}\n")
                f.flush()
        except Exception:  # noqa: S110
            pass

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Verify the vn-bridge Docker service is reachable and healthy."""
        self._log(f"Checking vn-bridge health at {BRIDGE_URL}/health ...")
        deadline = time.time() + _START_DEADLINE
        while time.time() < deadline:
            try:
                resp = urllib.request.urlopen(f"{BRIDGE_URL}/health", timeout=_HEALTH_TIMEOUT)  # noqa: S310
                data = json.loads(resp.read())
                if data.get("status") == "ok":
                    self._log("vn-bridge healthy — connected to agents.")
                    self.is_running = True
                    return True
                self._log(f"vn-bridge not ready yet: {data}")
            except Exception as e:
                self._log(f"Health check attempt failed: {e}")
            time.sleep(0.5)

        self._log("vn-bridge did not become healthy in time.")
        self.errors.put(
            "vn-bridge service unreachable at http://localhost:10010. "
            "Run `docker compose up` first."
        )
        return False

    def shutdown(self) -> None:
        self.is_running = False
        self._log("Bridge shutdown.")

    # ── Messaging ─────────────────────────────────────────────────────────

    def send_message(self, msg: dict) -> bool:
        """Route message to /action (sync) or /message (streaming) in a background thread."""
        if not self.is_running:
            self._log("send_message called but bridge not running")
            return False

        action = msg.get("action", "")
        if action in ("message", "choice"):
            t = threading.Thread(target=self._post_streaming, args=(msg,), daemon=True)
        else:
            t = threading.Thread(target=self._post_action, args=(msg,), daemon=True)
        t.start()
        return True

    def _post_action(self, msg: dict) -> None:
        """POST to /action, put single JSON response in inbox."""
        url = f"{BRIDGE_URL}/action"
        body = json.dumps(msg).encode("utf-8")
        self._log(f"POST /action: {json.dumps(msg)[:120]}")
        try:
            req = urllib.request.Request(  # noqa: S310
                url, data=body, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=_ACTION_TIMEOUT) as resp:  # noqa: S310
                result = json.loads(resp.read())
                self._log(f"Action result: {json.dumps(result)[:120]}")
                self.inbox.put(result)
        except Exception as e:
            self._log(f"POST /action error: {e}")
            self.errors.put(f"Action error: {e}")

    def _post_streaming(self, msg: dict) -> None:
        """POST to /message, stream NDJSON response into inbox."""
        url = f"{BRIDGE_URL}/message"
        body = json.dumps(msg).encode("utf-8")
        self._log(f"POST /message: {json.dumps(msg)[:120]}")
        try:
            req = urllib.request.Request(  # noqa: S310
                url, data=body, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=_MESSAGE_TIMEOUT) as resp:  # noqa: S310
                while True:
                    line = resp.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8").strip()
                    if not decoded:
                        continue
                    self._log(f"RECV: {decoded[:100]}")
                    try:
                        self.inbox.put(json.loads(decoded))
                    except json.JSONDecodeError:
                        self._log(f"Bad JSON line: {decoded}")
        except Exception as e:
            self._log(f"Streaming error: {e}")
            self.errors.put(f"Streaming error: {e}")

    def get_message(self, timeout: float = 0.1) -> dict | None:
        """Poll inbox for next agent response (non-blocking if timeout=0)."""
        try:
            return self.inbox.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_error(self, timeout: float = 0.0) -> str | None:
        """Poll error queue."""
        try:
            return self.errors.get(timeout=timeout)
        except queue.Empty:
            return None

    # ── TTS ────────────────────────────────────────────────────────────────

    def request_tts(self, text: str, agent: str) -> tuple[str, float | None] | None:
        """Request TTS audio from the bridge and save to game/audio/tts/.

        Returns ``(path, duration_seconds)`` on success — path is a
        Ren'Py-relative location (e.g. "audio/tts/tts_techne.mp3")
        suitable for ``renpy.voice()``; duration is parsed from the
        ``X-TTS-Duration-Seconds`` response header (M20 sub-task 2 VN
        surface) and is ``None`` if the bridge omitted it (older bridge
        version, malformed WAV). Callers wanting audio-led ``cps``
        pacing fall back to Ren'Py's default cps when duration is None.

        Returns ``None`` on transport failure.
        """
        url = f"{BRIDGE_URL}/tts"
        body = json.dumps({"text": text, "agent": agent}).encode("utf-8")
        try:
            req = urllib.request.Request(  # noqa: S310
                url, data=body, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=_ACTION_TIMEOUT) as resp:  # noqa: S310
                if resp.status != 200:
                    self._log(f"TTS request failed: HTTP {resp.status}")
                    return None
                audio_data = resp.read()
                if not audio_data:
                    self._log("TTS returned empty audio")
                    return None
                duration = self._parse_duration_header(resp)
                # game/audio/tts/ — Ren'Py resolves audio relative to game/
                audio_dir = self.game_dir / "audio" / "tts"
                audio_dir.mkdir(parents=True, exist_ok=True)
                filename = f"tts_{agent}.mp3"
                (audio_dir / filename).write_bytes(audio_data)
                self._log(f"TTS saved: {filename} ({len(audio_data)} bytes, duration={duration})")
                return f"audio/tts/{filename}", duration
        except Exception as e:
            self._log(f"TTS request error: {e}")
            return None

    @staticmethod
    def _parse_duration_header(resp) -> float | None:
        """Pull ``X-TTS-Duration-Seconds`` from the response. Returns
        None if the header is missing or unparseable — callers fall
        back to Ren'Py's global cps.
        """
        raw = resp.headers.get("X-TTS-Duration-Seconds")
        if not raw:
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    # ── Gossip ──────────────────────────────────────────────────────────────

    _GOSSIP_TIMEOUT = 5.0

    def request_gossip(self, agent: str, player_id: str, affinity: dict) -> tuple[str, str] | None:
        """Request a live gossip line from an idle agent.

        Returns (hint, line) tuple on success, None on failure.
        Callers should fall back to pre-authored GOSSIP_LINES on None.
        """
        url = f"{BRIDGE_URL}/gossip"
        body = json.dumps(
            {
                "agent": agent,
                "player_id": player_id,
                "affinity": affinity,
            }
        ).encode("utf-8")
        try:
            req = urllib.request.Request(  # noqa: S310
                url, data=body, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self._GOSSIP_TIMEOUT) as resp:  # noqa: S310
                if resp.status != 200:
                    self._log(f"Gossip request failed: HTTP {resp.status}")
                    return None
                data = json.loads(resp.read())
                hint = data.get("hint", "*observing*")
                line = data.get("line", "")
                if not line:
                    self._log("Gossip returned empty line")
                    return None
                self._log(f"Live gossip ({agent}): {hint} {line[:60]}")
                return (hint, line)
        except Exception as e:
            self._log(f"Gossip request error: {e}")
            return None

    # ── Ren'Py save/load pickle support ───────────────────────────────────

    def __getstate__(self) -> dict:
        return {"agent_script": self.agent_script}

    def __setstate__(self, state: dict) -> None:
        self.__init__(agent_script=state.get("agent_script", "agents/vn_bridge"))
