"""Slash command completer for the CLI REPL.

Renders a Claude Code-style popup menu when input begins with ``/``.
Live-filters as the user types, shows argument hints inline, and replaces
the typed prefix with the chosen command on accept.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import FormattedText

if TYPE_CHECKING:
    from collections.abc import Iterable

    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document


@dataclass(frozen=True)
class SlashCommand:
    """One entry in the slash menu (single source of truth for help + popup)."""

    name: str  # "project new" — no leading slash
    description: str  # one-line summary shown as popup meta
    arg_hint: str = ""  # e.g. "<name> [--template python]"

    @property
    def full(self) -> str:
        return f"/{self.name}"


SLASH_COMMANDS: tuple[SlashCommand, ...] = (
    SlashCommand("help", "Show command help and keyboard shortcuts"),
    SlashCommand(
        "settings",
        "Toggle voice, music, romance, and game systems",
        arg_hint="[1-9]",
    ),
    SlashCommand("config", "Alias for /settings", arg_hint="[1-9]"),
    SlashCommand("model_tier", "Show current provider, tier, and model"),
    SlashCommand("metrics", "Show alignment, affinity, and virtue metrics"),
    SlashCommand("maidens", "Meet the Golden Maidens", arg_hint="[name]"),
    SlashCommand("status", "Agent info: name, URL, model, context ID"),
    SlashCommand(
        "project new",
        "Forge a new player project",
        arg_hint="<name> [--template python|node|backend|frontend|empty]",
    ),
    SlashCommand("project list", "List all your player projects"),
    SlashCommand("project use", "Select an active project", arg_hint="<name|id>"),
    SlashCommand("project current", "Show the active project"),
    SlashCommand("project clear", "Clear the active project"),
    SlashCommand("project status", "Show pending forge sessions on active project"),
    SlashCommand(
        "project accept",
        "Merge a forge session into main (latest if no id given)",
        arg_hint="[session_id]",
    ),
    SlashCommand(
        "project discard",
        "Discard a forge session (latest if no id given)",
        arg_hint="[session_id]",
    ),
    SlashCommand(
        "project delete",
        "Delete a project from the registry",
        arg_hint="<name|id> [--purge]",
    ),
    SlashCommand("copy", "Copy last result to clipboard"),
    SlashCommand("save", "Save last result to a file", arg_hint="[filename]"),
    SlashCommand("clear", "Clear the screen"),
    SlashCommand("q", "Exit the CLI"),
    SlashCommand("quit", "Exit the CLI"),
    SlashCommand("exit", "Exit the CLI"),
)


class SlashCommandCompleter(Completer):
    """Popup completer for slash commands.

    Triggers when input starts with ``/``. Filters by prefix (then substring) on
    the command name as the user types. Each entry shows the command in gold,
    the optional argument hint dimmed, and the description as the popup meta
    column.
    """

    def __init__(self, commands: Iterable[SlashCommand] = SLASH_COMMANDS) -> None:
        self._commands: tuple[SlashCommand, ...] = tuple(commands)

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        text = document.text_before_cursor
        if not text.startswith("/"):
            return

        query = text[1:]
        if self._is_argument_input(query):
            return

        query_lower = query.lower()
        prefix_matches: list[SlashCommand] = []
        substring_matches: list[SlashCommand] = []
        for cmd in self._commands:
            name_lower = cmd.name.lower()
            if name_lower.startswith(query_lower):
                prefix_matches.append(cmd)
            elif query_lower and query_lower in name_lower:
                substring_matches.append(cmd)

        for cmd in (*prefix_matches, *substring_matches):
            display_parts: list[tuple[str, str]] = [("class:slash-cmd", cmd.full)]
            if cmd.arg_hint:
                display_parts.append(("", " "))
                display_parts.append(("class:slash-arg-hint", cmd.arg_hint))
            yield Completion(
                text=cmd.full + (" " if cmd.arg_hint else ""),
                start_position=-len(text),
                display=FormattedText(display_parts),
                display_meta=cmd.description,
            )

    def _is_argument_input(self, query: str) -> bool:
        """True once the user has typed a complete command name plus a space.

        Suppresses the popup so it doesn't get in the way during arg entry,
        unless there are still longer commands that share the prefix
        (e.g. ``/project `` should still show project subcommands).
        """
        for cmd in self._commands:
            prefix = cmd.name + " "
            if query.startswith(prefix):
                return not any(other.name.startswith(prefix) for other in self._commands)
        return False


__all__ = ["SLASH_COMMANDS", "SlashCommand", "SlashCommandCompleter"]
