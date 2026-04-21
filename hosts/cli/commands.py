"""REPL command dispatch — help, clipboard, key bindings, and command handlers.

All slash-prefixed commands (/help, /copy, /save, etc.) are handled here.
"""

from __future__ import annotations

import base64
import io as _io
import logging
import shutil
import subprocess
import sys

from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import has_completions, has_focus
from prompt_toolkit.key_binding import KeyBindings

from hosts.cli.rendering import _echo
from hosts.cli.settings import CLISettings
from hosts.cli.styling import (
    _DIM,
    _GOLD,
    _GOLD_BOLD,
    _GOLD_BRIGHT,
    _RED,
    _RESET,
)
from kourai_common.forge_session import (
    ForgeSession,
    ForgeSessionError,
    find_session,
    list_active_sessions,
)
from kourai_common.player import PlayerProfile
from kourai_common.player_memory import wipe_player_memories
from kourai_common.projects import KNOWN_TEMPLATES, ProjectError, ProjectManager

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


_SETTINGS_MAPPING: dict[str, str] = {
    "1": "voice_enabled",
    "2": "music_enabled",
    "3": "ambient_enabled",
    "4": "romance_enabled",
    "5": "gossip_enabled",
    "6": "metrics_tracking_enabled",
    "7": "romance_nudges_enabled",
    "8": "gossip_nudges_enabled",
}
_SETTINGS_LABELS: dict[str, str] = {
    "voice_enabled": "Voice",
    "music_enabled": "Background Music",
    "ambient_enabled": "Forge Ambience",
    "romance_enabled": "Romance System",
    "gossip_enabled": "Idle Gossip",
    "metrics_tracking_enabled": "Metrics Tracking",
    "romance_nudges_enabled": "Romance Nudges",
    "gossip_nudges_enabled": "Gossip Nudges",
}


def _print_settings_panel(settings: CLISettings) -> None:
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


def _apply_settings_choice(choice: str) -> bool:
    """Apply one settings choice. Returns True if anything changed."""
    settings = CLISettings.load()
    if choice in _SETTINGS_MAPPING:
        key = _SETTINGS_MAPPING[choice]
        new_val = settings.toggle(key)
        _echo(
            f"\n  {_GOLD_BRIGHT}\u2728 {_SETTINGS_LABELS[key]} is now "
            f"{'ON' if new_val else 'OFF'}{_RESET}"
        )
        _echo(f"  {_DIM}Applied immediately for this session.{_RESET}")
        return True
    if choice == "9":
        _reset_progression_data()
        return True
    return False


def _show_settings(direct_choice: str | None = None) -> None:
    """Interactive settings menu.

    If ``direct_choice`` is given (from ``/settings <n>``), apply it and return
    without reading stdin. Otherwise prompt with ``input()``; a slash-prefixed
    response closes silently since the user clearly meant a command.
    """
    settings = CLISettings.load()
    if direct_choice is not None:
        if not _apply_settings_choice(direct_choice.strip()):
            _print_settings_panel(settings)
            _echo(
                f"\n  {_DIM}Unknown option {direct_choice!r}. Use /settings for the menu.{_RESET}"
            )
        return

    _print_settings_panel(settings)
    _echo(f"\n  {_DIM}Type a number to change, or press Enter to close.{_RESET}")
    choice = input(f"  {_GOLD}Choice:{_RESET} ").strip()
    if not choice or choice.startswith("/"):
        # Empty → user pressed Enter; slash-prefix → user aimed at a slash
        # command. Either way, close silently and let the REPL handle it.
        return
    if not _apply_settings_choice(choice):
        _echo(f"\n  {_DIM}Invalid choice. Settings closed.{_RESET}")


# ---------------------------------------------------------------------------
# Player projects
# ---------------------------------------------------------------------------
def _project_usage_text() -> str:
    """Build the project subcommand usage block from the slash registry."""
    from hosts.cli.completer import SLASH_COMMANDS

    lines: list[str] = []
    for cmd in SLASH_COMMANDS:
        if not cmd.name.startswith("project"):
            continue
        line = f"  /{cmd.name}"
        if cmd.arg_hint:
            line += f" {cmd.arg_hint}"
        lines.append(line)
    return "\n".join(lines)


_PROJECT_USAGE = _project_usage_text()


def _active_project(settings: CLISettings):  # type: ignore[no-untyped-def]
    """Return the currently selected Project, or None if none/missing."""
    if not settings.active_project_id:
        return None
    return ProjectManager.get(settings.active_project_id)


def _parse_template_flag(args: list[str]) -> tuple[list[str], str]:
    """Pull --template <value> out of a flat arg list. Default 'empty'."""
    template = "empty"
    out: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--template", "-t") and i + 1 < len(args):
            template = args[i + 1]
            i += 2
            continue
        out.append(a)
        i += 1
    return out, template


def _player_id() -> str | None:
    profile = PlayerProfile.load()
    return profile.player_id if profile else None


def _handle_project_command(prompt_text: str, settings: CLISettings) -> None:
    """Dispatch `/project ...` subcommands. Mutates settings (active_project_id)."""
    parts = prompt_text.split()
    sub = parts[1].lower() if len(parts) > 1 else ""
    args = parts[2:]

    player_id = _player_id()
    if player_id is None:
        _echo(f"  {_RED}No active player profile \u2014 run onboarding first.{_RESET}")
        return

    if sub in ("", "help", "-h", "--help"):
        _echo(f"\n{_GOLD_BOLD}\u2501\u2501\u2501 Project commands \u2501\u2501\u2501{_RESET}")
        _echo(_PROJECT_USAGE)
        return

    if sub == "new":
        positional, template = _parse_template_flag(args)
        if not positional:
            _echo(f"  {_DIM}Usage: /project new <name> [--template <t>]{_RESET}")
            return
        name = " ".join(positional)
        try:
            project = ProjectManager.create(player_id, name, template=template)
        except ProjectError as exc:
            _echo(f"  {_RED}{exc}{_RESET}")
            return
        settings.active_project_id = project.project_id
        settings.save()
        _echo(
            f"  {_GOLD_BRIGHT}\u2728 Forged new project '{project.name}'"
            f" ({project.template}){_RESET}"
        )
        _echo(f"  {_DIM}Path: {project.path}{_RESET}")
        _echo(f"  {_DIM}Selected as active project.{_RESET}")
        return

    if sub == "list":
        projects = ProjectManager.list_for_player(player_id)
        if not projects:
            _echo(f"  {_DIM}No projects yet \u2014 /project new <name>{_RESET}")
            return
        active = settings.active_project_id
        for p in projects:
            marker = "*" if p.project_id == active else " "
            tmpl = p.template or "-"
            _echo(
                f"  {marker} {_GOLD}{p.name:<24}{_RESET} "
                f"{_DIM}{p.project_id[:8]}  {tmpl:<10}  {p.path}{_RESET}"
            )
        return

    if sub == "use":
        if not args:
            _echo(f"  {_DIM}Usage: /project use <name|id>{_RESET}")
            return
        target = " ".join(args)
        project = ProjectManager.find(player_id, target)
        if project is None:
            _echo(f"  {_RED}No project matches {target!r}{_RESET}")
            return
        settings.active_project_id = project.project_id
        settings.save()
        _echo(f"  {_GOLD_BRIGHT}\u2728 Active project: {project.name}{_RESET}")
        _echo(f"  {_DIM}{project.path}{_RESET}")
        return

    if sub == "current":
        project = _active_project(settings)
        if project is None:
            _echo(f"  {_DIM}No active project. /project use <name>{_RESET}")
            return
        _echo(f"  {_GOLD}Active:{_RESET} {project.name}")
        _echo(f"  {_DIM}{project.path}{_RESET}")
        return

    if sub == "delete":
        if not args:
            _echo(f"  {_DIM}Usage: /project delete <name|id> [--purge]{_RESET}")
            return
        purge = "--purge" in args
        target = " ".join(a for a in args if a != "--purge")
        project = ProjectManager.find(player_id, target)
        if project is None:
            _echo(f"  {_RED}No project matches {target!r}{_RESET}")
            return
        ProjectManager.delete(project.project_id, purge_files=purge)
        if settings.active_project_id == project.project_id:
            settings.active_project_id = None
            settings.save()
        suffix = " and files purged" if purge else ""
        _echo(f"  {_DIM}Deleted project '{project.name}'{suffix}.{_RESET}")
        return

    if sub == "clear":
        settings.active_project_id = None
        settings.save()
        _echo(f"  {_DIM}Active project cleared. Forge will run against cwd.{_RESET}")
        return

    if sub == "status":
        project = _active_project(settings)
        if project is None:
            _echo(f"  {_DIM}No active project. /project use <name>{_RESET}")
            return
        sessions = list_active_sessions(project.project_id)
        if not sessions:
            _echo(f"  {_DIM}No active forge sessions on '{project.name}'.{_RESET}")
            return
        _echo(f"  {_GOLD}Active forge sessions on '{project.name}':{_RESET}")
        for s in sessions:
            _echo(
                f"  - {_GOLD}{s.session_id[:8]}{_RESET} "
                f"{_DIM}branch={s.branch}  started={s.started_at}{_RESET}"
            )
        _echo(f"  {_DIM}Resolve with /project accept <id> or /project discard <id>{_RESET}")
        return

    if sub in ("accept", "discard"):
        project = _active_project(settings)
        if project is None:
            _echo(f"  {_RED}No active project.{_RESET}")
            return
        if args:
            session = find_session(project.project_id, args[0])
            if session is None:
                _echo(f"  {_RED}No active session matches {args[0]!r}{_RESET}")
                return
        else:
            # No id given → target the single active session; refuse if ambiguous.
            active = list_active_sessions(project.project_id)
            if not active:
                _echo(f"  {_DIM}No active session to {sub}.{_RESET}")
                return
            if len(active) > 1:
                _echo(
                    f"  {_DIM}Multiple active sessions — specify an id: "
                    f"/project {sub} <session_id>{_RESET}"
                )
                return
            session = active[0]
        try:
            if sub == "accept":
                session.accept()
                _echo(
                    f"  {_GOLD_BRIGHT}\u2728 Session {session.session_id[:8]} merged into main.{_RESET}"
                )
            else:
                session.discard()
                _echo(f"  {_DIM}Session {session.session_id[:8]} discarded.{_RESET}")
        except ForgeSessionError as exc:
            _echo(f"  {_RED}{exc}{_RESET}")
        return

    _echo(f"  {_DIM}Unknown /project subcommand: {sub!r}{_RESET}")
    _echo(_PROJECT_USAGE)


# Re-export for tests/external use.
__all__ = [
    "KNOWN_TEMPLATES",
    "_PROJECT_USAGE",
    "ForgeSession",
    "_active_project",
    "_build_key_bindings",
    "_copy_to_clipboard",
    "_handle_project_command",
    "_show_help",
    "_show_settings",
]


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------
def _show_help() -> None:
    from hosts.cli.completer import SLASH_COMMANDS

    _echo(f"\n{_GOLD_BOLD}\u2501\u2501\u2501 Kourai Khryseai Commands \u2501\u2501\u2501{_RESET}\n")
    _echo(
        f"  {_DIM}Type {_GOLD}/{_DIM} to open the slash menu — live filter, "
        f"\u2191\u2193 navigate, Tab/Enter accept, Esc dismiss{_RESET}\n"
    )

    entries = [
        (f"/{c.name}" + (f" {c.arg_hint}" if c.arg_hint else ""), c.description)
        for c in SLASH_COMMANDS
    ]
    col_width = max(len(name) for name, _ in entries) + 2
    for name, desc in entries:
        _echo(f"  {_GOLD}{name}{_RESET}{' ' * (col_width - len(name))}{_DIM}{desc}{_RESET}")

    _echo(f"""
{_GOLD_BOLD}\u2501\u2501\u2501 Keyboard Shortcuts \u2501\u2501\u2501{_RESET}

  {_GOLD}Enter{_RESET}              Send message (or accept highlighted slash command)
  {_GOLD}Tab{_RESET}                Autocomplete slash command
  {_GOLD}\u2191 / \u2193{_RESET}              Navigate slash menu
  {_GOLD}Esc{_RESET}                Dismiss slash menu
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

    @kb.add("enter", filter=has_completions & has_focus(DEFAULT_BUFFER))
    def _accept_completion(event) -> None:  # type: ignore[no-untyped-def]
        """Enter on a highlighted slash completion accepts it without submitting.

        Lets the user pick `/project new` from the popup and then type the name
        instead of immediately running an argument-less command.
        """
        buf = event.current_buffer
        state = buf.complete_state
        if state is not None and state.current_completion is not None:
            buf.apply_completion(state.current_completion)
        else:
            buf.validate_and_handle()

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
