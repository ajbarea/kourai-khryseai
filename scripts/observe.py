"""Open the observability UIs in the developer's default browser.

Cross-platform with WSL handling:

* macOS / Windows / native Linux desktops: :mod:`webbrowser` dispatches to
  the platform-native opener (``open`` / ``start`` / ``xdg-open``).
* WSL2 (no desktop session): :mod:`webbrowser` falls back to ``gio``, which
  can't open ``http://`` URLs without a real GNOME session. We bypass it
  and call ``wslview`` (from ``wslu``) when present, otherwise drop down
  to ``cmd.exe /c start`` via WSL interop -- always available at
  ``/mnt/c/Windows/System32/cmd.exe`` unless interop is disabled.

Usage:
    python scripts/observe.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

from kourai_common.dev_log import LOG

URLS: tuple[tuple[str, str, str], ...] = (
    (
        "Jaeger",
        "http://localhost:16686",
        'traces  — "where did this request go?" (A2A hops, MCP tool calls)',
    ),
    (
        "Prometheus",
        "http://localhost:9090",
        'metrics — "how often / how slow?" (rates, durations, counters)',
    ),
    (
        "Dozzle",
        "http://localhost:8888",
        'logs    — "what is THIS agent saying?" (per-container live tail)',
    ),
)


def _is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    proc_version = Path("/proc/version")
    if proc_version.exists():
        try:
            return "microsoft" in proc_version.read_text().lower()
        except OSError:
            return False
    return False


def _open_via_cmd_exe(url: str) -> bool:
    cmd_exe = shutil.which("cmd.exe") or "/mnt/c/Windows/System32/cmd.exe"
    if not Path(cmd_exe).exists():
        return False
    # `start` treats the first quoted arg as a window title; pass "" so the
    # URL is interpreted as the target. cwd=/mnt/c suppresses the harmless
    # UNC-path warning cmd.exe emits when invoked from a Linux working dir.
    result = subprocess.run(  # noqa: S603
        [cmd_exe, "/c", "start", "", url],
        cwd="/mnt/c",
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def open_url(url: str) -> bool:
    if sys.platform == "linux" and _is_wsl():
        if shutil.which("wslview"):
            result = subprocess.run(  # noqa: S603
                ["wslview", url], capture_output=True, check=False
            )
            return result.returncode == 0
        return _open_via_cmd_exe(url)
    return webbrowser.open(url, new=2, autoraise=True)


def main() -> int:
    failures: list[str] = []
    print("Opening observability UIs:")
    for name, url, scope in URLS:
        opened = open_url(url)
        marker = "+" if opened else "x"
        print(f"  {marker} {name:<11} {url:<24} {scope}")
        level = "INFO" if opened else "WARN"
        LOG.event(level, f"observe: {name} -> {url} ({'opened' if opened else 'failed'})")
        if not opened:
            failures.append(name)

    if failures:
        print()
        print(f"Could not open {len(failures)} tab(s): {', '.join(failures)}")
        if sys.platform == "linux" and _is_wsl():
            print("On WSL, install wslu for the cleanest path: sudo apt install wslu")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
