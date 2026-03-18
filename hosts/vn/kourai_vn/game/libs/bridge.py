"""Bridge between Ren'Py frontend and Python agent backend.

Manages subprocess communication, message queuing, and error handling.
Thread-safe for use from Ren'Py event loop.

Uses `uv run` to invoke the agent subprocess, matching the project's
standard approach. No manual venv path resolution needed.
"""

import contextlib
import datetime
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def _find_project_root() -> Path:
    """Walk parents from this file until we find pyproject.toml."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    # Fallback: assume the VN lives at hosts/vn/kourai_vn/game/libs/bridge.py
    # so project root is 4 levels up from this file
    return Path(__file__).resolve().parents[4]


class RenPyBridge:
    """IPC bridge using subprocess + JSON messages.

    Spawns `agents/vn_bridge.py` via `uv run` and communicates
    over stdin/stdout JSON lines.
    """

    def __init__(self, agent_script: str = "agents/vn_bridge.py"):
        self.agent_script = agent_script
        self.process: subprocess.Popen | None = None
        self.reader_thread: threading.Thread | None = None
        self.error_thread: threading.Thread | None = None
        self.is_running = False

        # Thread-safe queues
        self.inbox: queue.Queue[dict] = queue.Queue(maxsize=100)
        self.errors: queue.Queue[str] = queue.Queue()

        self.project_root = _find_project_root()
        self.log_dir = self.project_root / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "bridge_renpy.log"
        self.stderr_file = self.log_dir / "bridge_stderr.log"

    def _log(self, message: str) -> None:
        """Write to log file with flush."""
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {message}\n")
                f.flush()
        except Exception:  # noqa: S110 - logging unavailable, best effort only
            pass  # Silent fail; if logging is broken, stderr is our only option

    def start(self) -> bool:
        """Start the agent subprocess via uv run."""
        try:
            self._log("-" * 40)
            self._log(f"Starting bridge. Project root: {self.project_root}")

            # Verify uv is available
            uv_path = shutil.which("uv")
            if not uv_path:
                self._log("CRITICAL: uv not found on PATH")
                self.errors.put("uv not found on PATH. Install uv first.")
                return False
            self._log(f"Using uv: {uv_path}")

            # Build command: uv handles venv, deps, and PYTHONPATH
            # Direct script execution (agents/ is not a Python package)
            cmd = [
                uv_path,
                "run",
                "--no-active",
                "python",
                "-u",
                self.agent_script,
            ]
            self._log(f"Command: {' '.join(cmd)}")

            # Hide console window on Windows
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.process = subprocess.Popen(  # noqa: S603 - uv_path validated via shutil.which()
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(self.project_root),
                startupinfo=startupinfo,
            )

            # Give it time to fail early (uv sync, import errors, etc.)
            time.sleep(1.5)
            if self.process.poll() is not None:
                err = self.process.stderr.read() if self.process.stderr else "Unknown"
                self._log(f"Process DIED immediately: {err}")
                self.errors.put(f"Startup failed: {err}")
                return False

            self.is_running = True

            self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.reader_thread.start()
            self.error_thread = threading.Thread(target=self._error_loop, daemon=True)
            self.error_thread.start()

            self._log("Bridge threads spawned. Process running.")
            return True
        except Exception as e:
            self._log(f"EXCEPTION during start: {e}")
            self.errors.put(f"Exception: {e}")
            return False

    def _read_loop(self) -> None:
        """Read JSON lines from agent subprocess stdout."""
        try:
            if self.process and self.process.stdout:
                for line in self.process.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    self._log(f"RECV: {line}")
                    try:
                        msg = json.loads(line)
                        self.inbox.put(msg)
                    except json.JSONDecodeError:
                        self._log(f"FAIL JSON: {line}")
        except Exception as e:
            self._log(f"Reader thread error: {e}")
        finally:
            self.is_running = False

    def _error_loop(self) -> None:
        """Capture stderr from agent subprocess to log file."""
        try:
            if self.process and self.process.stderr:
                with open(self.stderr_file, "a", encoding="utf-8") as f:
                    for line in self.process.stderr:
                        ts = datetime.datetime.now().strftime("%H:%M:%S")
                        f.write(f"[{ts}] {line}")
                        f.flush()
                        self._log(f"STDERR: {line.strip()}")
        except Exception as e:
            self._log(f"Error thread error: {e}")

    def check_connection(self, timeout: float = 15.0) -> str | None:
        """Ping Hephaestus agent card to verify the swarm is reachable.

        Returns None on success, or an error string describing the failure.
        We cannot import kourai_common here (Ren'Py's Python, not uv env),
        so the port is hardcoded to match AGENT_PORTS["hephaestus"] = 10000.
        """
        url = "http://127.0.0.1:10000/.well-known/agent.json"
        self._log(f"Checking agent connection: GET {url}")
        try:
            req = urllib.request.urlopen(url, timeout=timeout)  # noqa: S310 - localhost only
            req.read()
            req.close()
            self._log("Agent connection check: OK")
            return None
        except urllib.error.HTTPError as e:
            msg = f"HTTP {e.code} from agent card endpoint"
            self._log(f"Connection check failed: {msg}")
            return msg
        except urllib.error.URLError as e:
            msg = f"Cannot reach agents at {url}: {e.reason}"
            self._log(f"Connection check failed: {msg}")
            return msg
        except Exception as e:
            msg = f"Unexpected error checking connection: {e}"
            self._log(f"Connection check failed: {msg}")
            return msg

    def send_message(self, msg: dict) -> bool:
        """Send a JSON message to the agent subprocess stdin."""
        if not self.is_running or not self.process or not self.process.stdin:
            return False
        try:
            line = json.dumps(msg) + "\n"
            self._log(f"SEND: {line.strip()}")
            self.process.stdin.write(line)
            self.process.stdin.flush()
            return True
        except Exception as e:
            self._log(f"Send error: {e}")
            return False

    def get_message(self, timeout: float = 0.1) -> dict | None:
        """Poll inbox for next agent response."""
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

    def shutdown(self) -> None:
        """Terminate the agent subprocess."""
        self.is_running = False
        if self.process:
            with contextlib.suppress(Exception):
                self.process.terminate()
        self._log("Bridge shutdown.")
