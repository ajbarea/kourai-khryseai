"""CLI gossip sidebar — text-based gossip display for terminal sessions.

Renders gossip sessions as inline text during task execution.
Uses ANSI colors to distinguish agents and response options.

Integration:
- Call `maybe_start_gossip()` when a task begins (provides busy agent name)
- Call `render_gossip_round()` to display new gossip messages
- Call `show_gossip_options()` to present response choices
- Call `handle_gossip_input()` to process player selection
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from kourai_common.gossip import (
    GossipResponseOption,
    GossipSession,
    ResponseTone,
    generate_gossip_round,
    generate_response_options,
    process_player_response,
    select_gossip_pair,
    start_gossip_session,
    summarize_gossip_session,
)
from kourai_common.player import PlayerProfile

log = logging.getLogger(__name__)

# ANSI color codes matching CLI theme
_RESET = "\033[0m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_ITALIC = "\033[3m"
_GOLD = "\033[38;5;220m"
_BLUE = "\033[38;5;75m"
_RED = "\033[38;5;203m"
_GREEN = "\033[38;5;114m"
_PINK = "\033[38;5;213m"
_CYAN = "\033[38;5;117m"

# Agent color map for gossip text
_AGENT_COLORS: dict[str, str] = {
    "hephaestus": "\033[38;5;208m",  # orange-gold
    "metis": "\033[38;5;229m",  # ivory-gold
    "techne": "\033[38;5;81m",  # sky blue
    "dokimasia": "\033[38;5;168m",  # rose
    "kallos": "\033[38;5;183m",  # lavender
    "mneme": "\033[38;5;156m",  # mint
}


def _agent_color(name: str) -> str:
    return _AGENT_COLORS.get(name, _GOLD)


def _format_gossip_header(session: GossipSession) -> str:
    """Format the gossip session header bar."""
    a_color = _agent_color(session.agent_a)
    b_color = _agent_color(session.agent_b)
    return (
        f"\n{_DIM}{'─' * 50}{_RESET}\n"
        f"{_DIM}💬 Gossip:{_RESET} "
        f"{a_color}{session.agent_a.title()}{_RESET}"
        f" {_DIM}&{_RESET} "
        f"{b_color}{session.agent_b.title()}{_RESET}"
        f"{_DIM}  (while agents work...){_RESET}\n"
        f"{_DIM}{'─' * 50}{_RESET}"
    )


def _format_gossip_message(agent_name: str, text: str) -> str:
    """Format a single gossip message with agent color."""
    color = _agent_color(agent_name)
    return f"  {color}{_BOLD}{agent_name.title()}{_RESET}: {_ITALIC}{text}{_RESET}"


def _format_response_options(options: list[GossipResponseOption]) -> str:
    """Format response options as a numbered list."""
    lines = [f"\n  {_DIM}Your response:{_RESET}"]
    for i, opt in enumerate(options, 1):
        if opt.tone == ResponseTone.IGNORE:
            lines.append(f"  {_DIM}  {i}. {opt.emoji} {opt.label} (press Enter){_RESET}")
        else:
            preview = f' — "{opt.preview_text}"' if opt.preview_text else ""
            lines.append(f"    {i}. {opt.emoji} {opt.label}{_DIM}{preview}{_RESET}")
    lines.append(f"  {_DIM}  c. ✏️  Custom response{_RESET}")
    return "\n".join(lines)


# ── Gossip lifecycle helpers ────────────────────────────────────────────


def maybe_start_gossip(
    busy_agent: str,
    profile: PlayerProfile | None = None,
) -> GossipSession | None:
    """Try to start a gossip session while an agent is busy.

    Args:
        busy_agent: Agent currently working (excluded from gossip).
        profile: Player profile for context.

    Returns:
        GossipSession if started, None if conditions not met.
    """
    pair = select_gossip_pair(busy_agent)
    if not pair:
        return None

    return start_gossip_session(pair[0], pair[1], profile=profile, max_rounds=2)


async def run_gossip_session_cli(
    session: GossipSession,
    profile: PlayerProfile | None = None,
    print_fn: Any = None,
    input_fn: Any = None,
) -> dict[str, Any]:
    """Run a complete gossip session in the CLI.

    Generates rounds, shows options, and processes player input.
    Returns the session summary.

    Args:
        session: Initialized gossip session.
        profile: Player profile for alignment scoring.
        print_fn: Output function (default: print). Accepts a string.
        input_fn: Input function (default: builtin input). Accepts prompt string.

    Returns:
        Session summary dict from summarize_gossip_session().
    """
    if print_fn is None:
        print_fn = print
    if input_fn is None:
        input_fn = input

    print_fn(_format_gossip_header(session))

    while not session.is_complete:
        # Generate a round of gossip
        messages = await generate_gossip_round(session, profile=profile)

        if not messages:
            break

        # Display messages with a brief pause between them
        for msg in messages:
            print_fn(_format_gossip_message(msg.agent_name, msg.text))
            await asyncio.sleep(0.3)

        if session.is_complete:
            break

        # Show response options
        options = generate_response_options(session, profile=profile)
        print_fn(_format_response_options(options))

        # Get player input
        try:
            choice = input_fn(f"  {_GOLD}>{_RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = ""

        if not choice:
            # Default to ignore — just keep listening
            continue

        if choice.lower() == "c":
            # Custom response
            try:
                custom = input_fn(f"  {_GOLD}Say:{_RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                continue
            if custom:
                reactions = await process_player_response(session, custom, profile=profile)
                for r in reactions:
                    print_fn(_format_gossip_message(r.agent_name, r.text))
                    await asyncio.sleep(0.2)
        else:
            # Numbered option
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    selected = options[idx]
                    if selected.tone == ResponseTone.IGNORE:
                        continue
                    print_fn(f"  {_PINK}{_ITALIC}You: {selected.preview_text}{_RESET}")
                    reactions = await process_player_response(session, selected, profile=profile)
                    for r in reactions:
                        print_fn(_format_gossip_message(r.agent_name, r.text))
                        await asyncio.sleep(0.2)
            except (ValueError, IndexError):
                print_fn(f"  {_DIM}(Invalid choice — the gossip continues...){_RESET}")

    print_fn(f"\n{_DIM}{'─' * 50}{_RESET}")
    print_fn(f"{_DIM}💬 Gossip ended.{_RESET}\n")

    return summarize_gossip_session(session)
