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
from hosts.cli.settings import CLISettings
from hosts.cli.styling import (
    _DIM,
    _GOLD,
    _GOLD_BOLD,
    _GOLD_BRIGHT,
    _RESET,
)
from kourai_common.player import PlayerProfile
from kourai_common.player_memory import wipe_player_memories

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Settings menu
# ---------------------------------------------------------------------------
def _reset_progression_data() -> None:
    """Reset progression-only data for the active profile."""
    profile = PlayerProfile.load()
    if profile is None:
        _echo(f"\n  {_DIM}No active profile to reset.{_RESET}")
        return

    _echo(f"\n  {_GOLD_BOLD}⚠ Reset progression data{_RESET}")
    _echo("  This keeps your identity/profile but clears:")
    _echo("  - Affinity + romance progression")
    _echo("  - Player memories")
    _echo("  - Alignment gauges (sovereignty/devotion)")
    confirm = input(f"  {_GOLD}Type RESET to confirm:{_RESET} ").strip()
    if confirm.upper() != "RESET":
        _echo(f"  {_DIM}Cancelled. No data changed.{_RESET}")
        return

    wipe_player_memories(profile.player_id)
    profile.sovereignty = 0
    profile.devotion = 0
    profile.romance_targets = []
    profile.save()
    _echo(f"  {_GOLD_BRIGHT}✨ Progression data reset complete.{_RESET}")


def _show_settings() -> None:
    """Show the interactive settings menu."""
    settings = CLISettings.load()

    _echo(f"\n{_GOLD_BOLD}\u2501\u2501\u2501 Forge Settings \u2501\u2501\u2501{_RESET}")
    _echo(f"  [1] Voice (TTS):    {'ON' if settings.voice_enabled else 'OFF'}")
    _echo(f"  [2] Background Mus: {'ON' if settings.music_enabled else 'OFF'}")
    _echo(f"  [3] Forge Ambience: {'ON' if settings.ambient_enabled else 'OFF'}")
    _echo(f"  [4] Romance System: {'ON' if settings.romance_enabled else 'OFF'}")
    _echo(f"  [5] Idle Gossip:    {'ON' if settings.gossip_enabled else 'OFF'}")
    _echo(f"  [6] Metrics Track:  {'ON' if settings.metrics_tracking_enabled else 'OFF'}")
    _echo(f"  [7] Romance Nudges: {'ON' if settings.romance_nudges_enabled else 'OFF'}")
    _echo(f"  [8] Gossip Nudges:  {'ON' if settings.gossip_nudges_enabled else 'OFF'}")
    _echo("  [9] Reset Progression Data")
    _echo(f"\n  {_DIM}Type a number to change, or press Enter to close.{_RESET}")

    choice = input(f"  {_GOLD}Choice:{_RESET} ").strip()

    mapping = {
        "1": "voice_enabled",
        "2": "music_enabled",
        "3": "ambient_enabled",
        "4": "romance_enabled",
        "5": "gossip_enabled",
        "6": "metrics_tracking_enabled",
        "7": "romance_nudges_enabled",
        "8": "gossip_nudges_enabled",
    }
    labels = {
        "voice_enabled": "Voice",
        "music_enabled": "Background Music",
        "ambient_enabled": "Forge Ambience",
        "romance_enabled": "Romance System",
        "gossip_enabled": "Idle Gossip",
        "metrics_tracking_enabled": "Metrics Tracking",
        "romance_nudges_enabled": "Romance Nudges",
        "gossip_nudges_enabled": "Gossip Nudges",
    }

    if choice in mapping:
        key = mapping[choice]
        new_val = settings.toggle(key)
        _echo(f"\n  {_GOLD_BRIGHT}\u2728 {labels[key]} is now {'ON' if new_val else 'OFF'}{_RESET}")
        _echo(f"  {_DIM}Applied immediately for this session.{_RESET}")
    elif choice == "9":
        _reset_progression_data()
    elif choice:
        _echo(f"\n  {_DIM}Invalid choice. Settings closed.{_RESET}")


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------
def _show_help() -> None:
    _echo(f"""
{_GOLD_BOLD}\u2501\u2501\u2501 Kourai Khryseai Commands \u2501\u2501\u2501{_RESET}

  {_GOLD}:help{_RESET} / {_GOLD}/help{_RESET}           Show this help
  {_GOLD}:settings{_RESET} / {_GOLD}/settings{_RESET}   Toggle voice, music, and game systems
  {_GOLD}:model_tier{_RESET} / {_GOLD}/model_tier{_RESET} Show current provider/tier/model
  {_GOLD}:metrics{_RESET} / {_GOLD}/metrics{_RESET}   Show alignment, affinity, and virtue metrics
  {_GOLD}:maidens{_RESET} / {_GOLD}/maidens{_RESET}     Meet the Golden Maidens
  {_GOLD}:status{_RESET} / {_GOLD}/status{_RESET}       Agent info, URL, model, context ID
  {_GOLD}:copy{_RESET} / {_GOLD}/copy{_RESET}           Copy last result to clipboard
  {_GOLD}:save{_RESET} / {_GOLD}/save <file>{_RESET}    Save last result to a file
  {_GOLD}:clear{_RESET} / {_GOLD}/clear{_RESET}         Clear the screen
  {_GOLD}:q{_RESET} / {_GOLD}quit{_RESET} / {_GOLD}exit{_RESET}      Exit the CLI

{_GOLD_BOLD}\u2501\u2501\u2501 Keyboard Shortcuts \u2501\u2501\u2501{_RESET}

  {_GOLD}Enter{_RESET}              Send message
  {_GOLD}Alt+Enter{_RESET}          New line (Shift+Enter or Esc+Enter)
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

    @kb.add("escape", "enter")  # Alt+Enter (or Esc+Enter)
    def _newline(event) -> None:  # type: ignore[no-untyped-def]
        """Insert a newline manually even in single-line mode."""
        event.app.current_buffer.insert_text("\n")

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
