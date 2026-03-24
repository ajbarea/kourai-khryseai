"""REPL command dispatch — help, clipboard, key bindings, and command handlers.

All colon-prefixed commands (:help, :copy, :save, etc.) are handled here.
"""

from __future__ import annotations

import base64
import io as _io
import logging
import shutil
import subprocess
import sys

from prompt_toolkit.key_binding import KeyBindings

from hosts.cli.rendering import _echo
from hosts.cli.styling import (
    _DIM,
    _GOLD,
    _GOLD_BOLD,
    _RESET,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------
def _show_help() -> None:
    _echo(f"""
{_GOLD_BOLD}\u2501\u2501\u2501 Kourai Khryseai Commands \u2501\u2501\u2501{_RESET}

  {_GOLD}:help{_RESET}              Show this help
  {_GOLD}:maidens{_RESET}           Meet the Golden Maidens
  {_GOLD}:maidens <name>{_RESET}   Show a specific maiden
  {_GOLD}:status{_RESET}            Agent info, URL, context ID
  {_GOLD}:copy{_RESET}              Copy last result to clipboard
  {_GOLD}:save <file>{_RESET}       Save last result to a file
  {_GOLD}:clear{_RESET}             Clear the screen
  {_GOLD}:q{_RESET} / {_GOLD}quit{_RESET} / {_GOLD}exit{_RESET}  Exit the CLI

{_GOLD_BOLD}\u2501\u2501\u2501 Keyboard Shortcuts \u2501\u2501\u2501{_RESET}

  {_GOLD}Alt+Enter{_RESET}          Send message
  {_GOLD}Ctrl+V{_RESET}             Paste text
  {_GOLD}Alt+V{_RESET}              Attach clipboard image

{_GOLD_BOLD}\u2501\u2501\u2501 Headless Mode \u2501\u2501\u2501{_RESET}

  {_DIM}uv run python -m hosts.cli -p "generate commit messages"{_RESET}
  {_DIM}uv run python -m hosts.cli -p "fix the bug" | pbcopy{_RESET}
""")


# ---------------------------------------------------------------------------
# Clipboard copy
# ---------------------------------------------------------------------------
def _copy_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard. Returns True on success."""
    try:
        if sys.platform == "win32":
            exe = shutil.which("clip")
            if not exe:
                return False
            proc = subprocess.Popen([exe], stdin=subprocess.PIPE)  # noqa: S603
            proc.communicate(text.encode("utf-16le"))
            return proc.returncode == 0
        elif sys.platform == "darwin":
            exe = shutil.which("pbcopy")
            if not exe:
                return False
            proc = subprocess.Popen([exe], stdin=subprocess.PIPE)  # noqa: S603
            proc.communicate(text.encode())
            return proc.returncode == 0
        else:
            # Linux — try xclip, then xsel
            for cmd_name in ("xclip", "xsel"):
                exe = shutil.which(cmd_name)
                if not exe:
                    continue

                args = [exe]
                if cmd_name == "xclip":
                    args.extend(["-selection", "clipboard"])
                elif cmd_name == "xsel":
                    args.extend(["--clipboard", "--input"])

                try:
                    proc = subprocess.Popen(args, stdin=subprocess.PIPE)  # noqa: S603
                    proc.communicate(text.encode())
                    if proc.returncode == 0:
                        return True
                except Exception:
                    logger.debug("Clipboard command %s failed", exe, exc_info=True)
                    continue
            return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Key bindings
# ---------------------------------------------------------------------------
def _build_key_bindings(pending_images: list[tuple[str, str]]) -> KeyBindings:
    """Build key bindings — Alt+V captures clipboard image as a queued attachment."""
    kb = KeyBindings()

    @kb.add("escape", "v")  # Alt+V in most terminals
    def _capture_image(event) -> None:  # type: ignore[no-untyped-def]
        """Read OS clipboard image, base64-encode it, queue as next-message attachment."""
        try:
            from PIL import ImageGrab  # type: ignore[import-untyped]

            img = ImageGrab.grabclipboard()
            if img is None:
                event.app.current_buffer.insert_text("[no image in clipboard]")
                return
            if isinstance(img, list):
                event.app.current_buffer.insert_text("[clipboard contains files, not an image]")
                return
            buf = _io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            pending_images.append((b64, "image/png"))
            event.app.current_buffer.insert_text(
                f"[\U0001f4ce image #{len(pending_images)} queued]"
            )
        except ImportError:
            event.app.current_buffer.insert_text("[Pillow not installed \u2014 run: uv add Pillow]")
        except Exception as exc:
            event.app.current_buffer.insert_text(f"[image capture failed: {exc}]")

    return kb
