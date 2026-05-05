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

from hosts.cli.mode_cascade import Mode, apply_mode_cascade, current_mode
from hosts.cli.rendering import _echo
from hosts.cli.settings import CLISettings
from hosts.cli.styling import (
    _DIM,
    _GOLD,
    _GOLD_BOLD,
    _GOLD_BRIGHT,
    _ITALIC,
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


def _confirm_project_delete(name: str, path: object, *, purge: bool) -> bool:
    """Prompt for confirmation before /project delete touches anything.

    Two tiers because the underlying ``ProjectManager.delete()`` has two
    very different blast radii:

    - **bare delete** removes only the SQLite registry row. The project
      files at ``path`` survive and can be re-added with
      ``/project new <name>`` against that path. Annoying-but-recoverable
      → simple ``[y/N]`` is enough.
    - **--purge** runs ``shutil.rmtree`` on ``path``. There is no
      recovery. Match the typed-name pattern used by
      ``_reset_progression_data`` ("Type DELETE <name> to confirm") so
      muscle-memory tab-completion can't nuke a real project.

    Returns True iff the user typed an affirmative response.
    """
    if purge:
        _echo("")
        _echo(f"  {_GOLD_BOLD}⚠ Permanently delete project files{_RESET}")
        _echo(f"  This will run rm -rf on {path}.")
        _echo(f"  {_RED}There is no undo.{_RESET}")
        confirm = input(f"  {_GOLD}Type DELETE {name} to confirm:{_RESET} ").strip()
        return confirm == f"DELETE {name}"

    _echo("")
    _echo(f"  {_GOLD_BOLD}Remove '{name}' from the project registry?{_RESET}")
    _echo(f"  {_DIM}Files at {path} will survive — only the registry row goes.{_RESET}")
    confirm = input(f"  {_GOLD}[y/N]:{_RESET} ").strip().lower()
    return confirm in ("y", "yes")


_SETTINGS_MAPPING: dict[str, str] = {
    "1": "voice_enabled",
    "2": "music_enabled",
    "3": "ambient_enabled",
    "4": "captions_enabled",
    "5": "romance_enabled",
    "6": "gossip_enabled",
    "7": "metrics_tracking_enabled",
    "8": "romance_nudges_enabled",
    "9": "gossip_nudges_enabled",
}
_SETTINGS_LABELS: dict[str, str] = {
    "voice_enabled": "Voice",
    "music_enabled": "Background Music",
    "ambient_enabled": "Forge Ambience",
    "captions_enabled": "Dialogue Captions",
    "romance_enabled": "Romance System",
    "gossip_enabled": "Idle Gossip",
    "metrics_tracking_enabled": "Metrics Tracking",
    "romance_nudges_enabled": "Romance Nudges",
    "gossip_nudges_enabled": "Gossip Nudges",
}


def _print_settings_panel(settings: CLISettings) -> None:
    _echo(f"\n{_GOLD_BOLD}\u2501\u2501\u2501 Forge Settings \u2501\u2501\u2501{_RESET}")
    _echo(f"  [0] Session Mode:   {current_mode()}")
    _echo(
        f"  [1] Voice (TTS):    {'ON' if settings.voice_enabled else 'OFF'}"
        f"  {_DIM}vol {settings.voice_volume:.2f}{_RESET}"
    )
    _echo(
        f"  [2] Background Mus: {'ON' if settings.music_enabled else 'OFF'}"
        f"  {_DIM}vol {settings.music_volume:.2f}{_RESET}"
    )
    _echo(
        f"  [3] Forge Ambience: {'ON' if settings.ambient_enabled else 'OFF'}"
        f"  {_DIM}vol {settings.ambient_volume:.2f}{_RESET}"
    )
    _echo(f"  [4] Dialogue Caps:  {'ON' if settings.captions_enabled else 'OFF'}")
    _echo(f"  [5] Romance System: {'ON' if settings.romance_enabled else 'OFF'}")
    _echo(f"  [6] Idle Gossip:    {'ON' if settings.gossip_enabled else 'OFF'}")
    _echo(f"  [7] Metrics Track:  {'ON' if settings.metrics_tracking_enabled else 'OFF'}")
    _echo(f"  [8] Romance Nudges: {'ON' if settings.romance_nudges_enabled else 'OFF'}")
    _echo(f"  [9] Gossip Nudges:  {'ON' if settings.gossip_nudges_enabled else 'OFF'}")
    _echo(f"  [s] Sync Mode:      {settings.dialogue_sync_mode}")
    _echo("  [r] Reset Progression Data")
    _echo(f"  [v] Adjust volumes  {_DIM}(music / ambient / voice / sfx){_RESET}")


_VOLUME_PROMPTS: tuple[tuple[str, str], ...] = (
    ("music_volume", "Music"),
    ("ambient_volume", "Ambient"),
    ("voice_volume", "Voice"),
    ("sfx_volume", "SFX"),
)


def _adjust_volumes(settings: CLISettings) -> bool:
    """Walk through each volume prompt; press Enter to keep current.

    Returns True if any volume changed (caller re-applies audio settings).
    """
    _echo(
        f"\n  {_DIM}Adjust volumes \u2014 Enter to keep, decimals 0.0-1.0 "
        f"(percentages 0-100 also accepted):{_RESET}"
    )
    changed = False
    for key, label in _VOLUME_PROMPTS:
        current = getattr(settings, key)
        raw = input(f"  {_GOLD}{label:<7} [{current:.2f}]:{_RESET} ").strip()
        if not raw:
            continue
        try:
            value = float(raw)
        except ValueError:
            _echo(f"  {_DIM}Skipped {label}: not a number ({raw!r}).{_RESET}")
            continue
        # Accept 0-100 percent input as a convenience \u2014 anything > 1.0 is
        # treated as percent. set_volume clamps to [0.0, 1.0] for us.
        if value > 1.0:
            value = value / 100.0
        new_val = settings.set_volume(key, value)
        _echo(f"  {_GOLD_BRIGHT}\u2728 {label} volume \u2192 {new_val:.2f}{_RESET}")
        changed = True
    if changed:
        _echo(f"  {_DIM}Volumes saved.{_RESET}")
    return changed


def _apply_settings_choice(choice: str) -> bool:
    """Apply one settings choice. Returns True if anything changed."""
    settings = CLISettings.load()
    if choice == "0":
        # Puck-tutorial mode cascade — flips between gamified and
        # focused, writes all seven cascade settings across both stores.
        # Diegetic line per spec; in-fiction "Puck returns / forge
        # falls quiet" framing matches the onboarding mode-gate scene.
        active = current_mode()
        target: Mode = "focused" if active == "gamified" else "gamified"
        apply_mode_cascade(target)
        flavor = (
            "Puck slips back through the door, grinning."
            if target == "gamified"
            else "The forge falls quiet."
        )
        _echo(f"\n  {_GOLD_BRIGHT}✨ Session Mode is now {target}{_RESET}")
        _echo(f"  {_ITALIC}{flavor}{_RESET}")
        _echo(f"  {_DIM}Cascade applied to PlayerProfile + CLISettings.{_RESET}")
        return True
    if choice in _SETTINGS_MAPPING:
        key = _SETTINGS_MAPPING[choice]
        new_val = settings.toggle(key)
        _echo(
            f"\n  {_GOLD_BRIGHT}\u2728 {_SETTINGS_LABELS[key]} is now "
            f"{'ON' if new_val else 'OFF'}{_RESET}"
        )
        _echo(f"  {_DIM}Applied immediately for this session.{_RESET}")
        return True
    if choice.lower() == "s":
        # M20 sub-task 4 \u2014 cycle dialogue_sync_mode through its two
        # values. Bool toggle() doesn't fit a string field, so handle
        # explicitly here.
        new_val = "instant" if settings.dialogue_sync_mode == "audio-led" else "audio-led"
        settings.dialogue_sync_mode = new_val
        settings.save()
        _echo(f"\n  {_GOLD_BRIGHT}\u2728 Dialogue Sync Mode is now {new_val}{_RESET}")
        _echo(f"  {_DIM}Applied to the next dialogue line.{_RESET}")
        return True
    if choice.lower() == "r":
        _reset_progression_data()
        return True
    if choice.lower() == "v":
        return _adjust_volumes(settings)
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


def _active_project_fact_id(settings: CLISettings) -> str | None:
    """Resolve the M17 fact-axis id from the active project's stable path.

    Bare ``settings.active_project_id`` is the registry uuid, NOT the
    fact axis. The fact axis is ``derive_project_id(project.path)`` —
    the same value the REPL stamps into the ``[project_id: …]`` forge
    tag — so the same id reads back in ``/preferences`` as it was
    written under during PAUSE-resolution.
    """
    project = _active_project(settings)
    if project is None:
        return None
    from kourai_common.projects import derive_project_id

    return derive_project_id(project.path)


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
            _echo(f"  {_DIM}Usage: /project delete <name|id> [--purge] [--yes]{_RESET}")
            return
        purge = "--purge" in args
        skip_confirm = "--yes" in args or "-y" in args
        target = " ".join(a for a in args if a not in ("--purge", "--yes", "-y"))
        project = ProjectManager.find(player_id, target)
        if project is None:
            _echo(f"  {_RED}No project matches {target!r}{_RESET}")
            return

        # Two-tier confirmation: bare `delete` removes the registry row
        # (recoverable — files survive at the path); --purge runs rm -rf
        # on the project directory (irreversible). Match the typed-name
        # pattern used by /settings → reset_progression for the
        # destructive case so muscle memory can't nuke a real project.
        if not skip_confirm:
            if not _confirm_project_delete(project.name, project.path, purge=purge):
                _echo(f"  {_DIM}Cancelled. No data changed.{_RESET}")
                return

        ProjectManager.delete(project.project_id, purge_files=purge)
        if settings.active_project_id == project.project_id:
            settings.active_project_id = None
            settings.save()
        if purge:
            _echo(f"  {_DIM}Deleted project '{project.name}' and purged {project.path}.{_RESET}")
        else:
            _echo(
                f"  {_DIM}Removed '{project.name}' from the registry. "
                f"Files survive at {project.path} — re-add with "
                f"`/project new <name>` against that path to restore.{_RESET}"
            )
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


# ---------------------------------------------------------------------------
# /preferences — M17 Phase 2 item 7
# ---------------------------------------------------------------------------
_PREFERENCES_USAGE = (
    "  /preferences                list stored preference facts\n"
    "  /preferences set <kind> <value>\n"
    "  /preferences forget <kind>  forget the active scope's value for <kind>\n"
    "  /preferences forget --all   forget every preference for the active scope\n"
    "\n"
    "  Aliases: /prefs"
)


def _handle_preferences_command(prompt_text: str, settings: CLISettings) -> None:
    """Browse, override, and forget closed-vocab preference facts.

    M17 Phase 2 item 7. Mirrors the ``/permissions`` shape: bare command
    lists everything; named subcommands (``set`` / ``forget``) mutate.

    The active scope is the M17 fact axis derived from the active
    project's persistent path (NOT the per-session forge worktree).
    Without an active project, scope falls back to global so a player
    can still curate cross-project preferences.

    Right-to-forget is non-negotiable here: every fact is removable by
    the player, with no operator gate. ``forget --all`` clears every
    preference fact for the active scope in one move.
    """
    from kourai_common.facts import (
        forget_preference_fact,
        list_preference_facts,
        set_preference_fact,
    )
    from kourai_common.hooks_interaction import VALID_PREFERENCE_KINDS

    parts = prompt_text.split()
    sub = parts[1].lower() if len(parts) > 1 else ""
    args = parts[2:]

    player_id = _player_id()
    if player_id is None:
        _echo(f"  {_RED}No active player profile — run onboarding first.{_RESET}")
        return

    project_id = _active_project_fact_id(settings)
    project = _active_project(settings)
    scope_label = (
        f"project '{project.name}'" if project is not None else "global (no active project)"
    )

    if sub in ("help", "-h", "--help"):
        _echo(f"\n{_GOLD_BOLD}━━━ Preferences ━━━{_RESET}")
        _echo(_PREFERENCES_USAGE)
        _echo(f"\n  {_DIM}Closed vocabulary: {', '.join(sorted(VALID_PREFERENCE_KINDS))}{_RESET}")
        return

    if sub == "set":
        if len(args) < 2:
            _echo(f"  {_DIM}Usage: /preferences set <kind> <value>{_RESET}")
            _echo(f"  {_DIM}Valid kinds: {', '.join(sorted(VALID_PREFERENCE_KINDS))}{_RESET}")
            return
        kind = args[0].lower()
        value = " ".join(args[1:]).strip()
        if kind not in VALID_PREFERENCE_KINDS:
            _echo(f"  {_RED}Unknown preference kind: {kind!r}{_RESET}")
            _echo(f"  {_DIM}Valid kinds: {', '.join(sorted(VALID_PREFERENCE_KINDS))}{_RESET}")
            return
        ok = set_preference_fact(
            player_id=player_id,
            project_id=project_id,
            kind=kind,
            value=value,
        )
        if not ok:
            _echo(f"  {_RED}Could not store {kind} — value rejected.{_RESET}")
            return
        _echo(f"  {_GOLD_BRIGHT}✨ {kind} set to {value!r}{_RESET} {_DIM}({scope_label}){_RESET}")
        return

    if sub == "forget":
        if not args:
            _echo(f"  {_DIM}Usage: /preferences forget <kind|--all>{_RESET}")
            return
        if args[0] == "--all":
            removed = 0
            for kind in sorted(VALID_PREFERENCE_KINDS):
                removed += forget_preference_fact(player_id, project_id, kind)
            _echo(
                f"  {_GOLD}Forgot {removed} preference{'s' if removed != 1 else ''}{_RESET}"
                f" {_DIM}from {scope_label}.{_RESET}"
            )
            return
        kind = args[0].lower()
        # Tolerate a kind that's been retired from VALID_PREFERENCE_KINDS:
        # right-to-forget must outlive vocab churn.
        removed = forget_preference_fact(player_id, project_id, kind)
        if removed == 0:
            _echo(f"  {_DIM}No {kind} preference stored for {scope_label}.{_RESET}")
            return
        _echo(
            f"  {_GOLD}Forgot {kind}{_RESET}"
            f" {_DIM}({removed} row{'s' if removed != 1 else ''} from {scope_label}).{_RESET}"
        )
        return

    if sub and sub != "list":
        _echo(f"  {_DIM}Unknown /preferences subcommand: {sub!r}{_RESET}")
        _echo(_PREFERENCES_USAGE)
        return

    # Bare /preferences (or /preferences list): show everything that
    # would surface to specialists in the active scope.
    rows = list_preference_facts(player_id, project_id=project_id)
    _echo(f"\n  {_GOLD_BRIGHT}━━━ Preferences ━━━{_RESET}")
    _echo(f"  {_DIM}Scope: {scope_label}{_RESET}")
    if not rows:
        _echo(
            f"  {_DIM}No preferences stored yet — set one with "
            f"/preferences set <kind> <value>.{_RESET}"
        )
        return
    kind_width = max(len(r["kind"]) for r in rows) + 2
    for row in rows:
        marker = "*" if row["scope"] == "project" else " "
        _echo(
            f"  {marker} {_GOLD}{row['kind']:<{kind_width}}{_RESET}"
            f"{row['value']}  {_DIM}({row['scope']}, "
            f"from {row['source_agent']}){_RESET}"
        )
    _echo(f"\n  {_DIM}Forget with /preferences forget <kind> or /preferences forget --all.{_RESET}")


# Re-export for tests/external use.
__all__ = [
    "KNOWN_TEMPLATES",
    "_PREFERENCES_USAGE",
    "_PROJECT_USAGE",
    "ForgeSession",
    "_active_project",
    "_active_project_fact_id",
    "_build_key_bindings",
    "_copy_to_clipboard",
    "_handle_preferences_command",
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
