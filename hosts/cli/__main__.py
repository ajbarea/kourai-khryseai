"""Kourai Khryseai CLI — interactive client for the agent swarm.

Connects to Hephaestus (orchestrator) and streams pipeline progress
with agent-prefixed emoji status messages.

Usage: python -m hosts.cli [--agent URL] [--verbose] [-p PROMPT]
"""

from __future__ import annotations

import asyncio
import io as _io
import secrets
import sys
from uuid import uuid4

import asyncclick as click
import httpx
from a2a.client import ClientConfig
from anyio import Path as AnyioPath
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.patch_stdout import patch_stdout

from hosts.cli.commands import _build_key_bindings, _copy_to_clipboard, _show_help
from hosts.cli.events import (  # noqa: F401 — re-exported for backward compat
    _extract_artifact_text,
    _extract_status_text,
)
from hosts.cli.headless import _headless
from hosts.cli.maidens import _MAIDEN_FACES, _MAIDENS
from hosts.cli.rendering import _banner, _echo, _maiden_card, _maiden_gallery, set_raw_out
from hosts.cli.streaming import _connect_with_url_override, get_last_result, send_and_stream
from hosts.cli.styling import _DIM, _GOLD, _GOLD_BRIGHT, _ITALIC, _RED, _RESET
from kourai_common.config import get_agent_url

# Windows consoles default to cp1252 — force UTF-8 so emoji and box-drawing work.
# Skip when imported under pytest — replacing streams breaks pytest's capture system.
if sys.platform == "win32" and hasattr(sys.stdout, "buffer") and "pytest" not in sys.modules:
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Save a reference to the real stdout BEFORE prompt_toolkit's patch_stdout
# can wrap it.  Dense ANSI (pixel art, true-color) gets mangled by
# prompt_toolkit's VT parser on Windows — writing to the real stdout
# bypasses that entirely.  Safe because we only _echo() between prompts,
# never while the prompt is being displayed.
set_raw_out(sys.stdout)


# ---------------------------------------------------------------------------
# Main CLI entry point
# ---------------------------------------------------------------------------
@click.command()
@click.option(
    "--agent",
    default=None,
    help="Hephaestus URL (default: auto from config)",
)
@click.option(
    "--timeout",
    "timeout_seconds",
    default=600,
    help="Request timeout in seconds",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show timing and debug details",
)
@click.option(
    "--prompt",
    "-p",
    default=None,
    help="Run a single prompt non-interactively (headless mode)",
)
async def main(agent: str | None, timeout_seconds: int, verbose: bool, prompt: str | None) -> None:
    """Interactive CLI for Kourai Khryseai agent swarm."""
    if not agent:
        agent = get_agent_url("hephaestus")

    # Headless mode — run a single prompt and exit (for scripts / piping)
    if prompt:
        await _headless(agent, prompt, timeout_seconds, verbose)
        return

    _echo(_banner())

    # First-run onboarding — collect player identity before connecting
    from hosts.cli.onboarding import increment_session, needs_onboarding, run_onboarding

    if needs_onboarding():
        run_onboarding()
    else:
        increment_session()

    _echo(f"Connecting to Hephaestus at {agent}...")

    config = ClientConfig(
        streaming=True,
        httpx_client=httpx.AsyncClient(timeout=timeout_seconds),
    )

    try:
        client = await _connect_with_url_override(agent, config)
    except httpx.ConnectError:
        _echo(f"{_RED}\U0001f525 Cannot reach Hephaestus at {agent}{_RESET}")
        _echo(f"Start the forge with: {_GOLD}make up{_RESET}")
        sys.exit(1)
    except Exception as e:
        _echo(f"{_RED}Failed to connect: {e}{_RESET}")
        sys.exit(1)

    card = await client.get_card()
    _echo(f"Connected to {_GOLD}{card.name}{_RESET} v{card.version}")
    _echo(f"Skills: {_DIM}{', '.join(s.name for s in card.skills)}{_RESET}")
    if verbose:
        _echo(f"{_DIM}[verbose] URL={agent} streaming={card.capabilities.streaming}{_RESET}")

    # Random maiden greeting on startup — maidens flirt with the user,
    # Hephaestus is gruff but welcoming. user_quotes are the warm ones.
    _greet_name = secrets.choice(list(_MAIDENS.keys()))
    _greet_m = _MAIDENS[_greet_name]
    _greet_quotes = _greet_m.get("user_quotes", _greet_m["quotes"])
    _greet_quote = secrets.choice(_greet_quotes)
    _echo(f"\n  {_GOLD}{_MAIDEN_FACES[_greet_name]}{_RESET} {_ITALIC}{_greet_quote}{_RESET}")
    _echo("")

    context_id: str = uuid4().hex
    pending_images: list[tuple[str, str]] = []  # (base64_bytes, mime_type)
    kb = _build_key_bindings(pending_images)
    session: PromptSession[str] = PromptSession(key_bindings=kb, multiline=True)

    def _toolbar() -> str:
        img = f"  \U0001f4ce {len(pending_images)} image(s) queued" if pending_images else ""
        return f"Alt+Enter send  \u00b7  Alt+V attach image  \u00b7  :help  \u00b7  :q quit{img}"

    try:
        with patch_stdout():
            while True:
                try:
                    prompt_text = await session.prompt_async(
                        ANSI(f"{_GOLD}\u276f{_RESET} "),
                        bottom_toolbar=_toolbar,
                    )
                except (EOFError, KeyboardInterrupt):
                    _echo(f"\n{_GOLD}Farewell from the forge! \u2728{_RESET}")
                    break

                prompt_text = prompt_text.strip()

                if prompt_text.lower() in (":q", "quit", "exit"):
                    _echo(f"{_GOLD}Farewell from the forge! \u2728{_RESET}")
                    break

                # --- Command dispatch ---
                if prompt_text == ":help":
                    _show_help()
                    continue

                if prompt_text.startswith(":maidens"):
                    _parts = prompt_text.split(maxsplit=1)
                    if len(_parts) > 1:
                        _mname = _parts[1].strip().lower()
                        if _mname in _MAIDENS:
                            _echo("\n" + _maiden_card(_mname))
                        else:
                            _echo(
                                f"{_DIM}Unknown maiden: {_mname}. "
                                f"Try: {', '.join(_MAIDENS.keys())}{_RESET}"
                            )
                    else:
                        _echo(_maiden_gallery())
                    continue

                if prompt_text == ":status":
                    _echo(f"  {_GOLD}Agent:{_RESET}     {card.name} v{card.version}")
                    _echo(f"  {_GOLD}URL:{_RESET}       {agent}")
                    _echo(f"  {_GOLD}Context:{_RESET}   {context_id}")
                    _echo(f"  {_GOLD}Streaming:{_RESET} {card.capabilities.streaming}")
                    continue

                if prompt_text == ":copy":
                    _last_result = get_last_result()
                    if not _last_result:
                        _echo(f"{_DIM}Nothing to copy yet \u2014 run a command first.{_RESET}")
                    elif _copy_to_clipboard(_last_result):
                        _echo(f"{_GOLD_BRIGHT}\u2728 Copied to clipboard!{_RESET}")
                    else:
                        _echo(f"{_RED}Clipboard copy failed \u2014 try :save instead{_RESET}")
                    continue

                if prompt_text.startswith(":save"):
                    _last_result = get_last_result()
                    if not _last_result:
                        _echo(f"{_DIM}Nothing to save yet \u2014 run a command first.{_RESET}")
                        continue
                    parts_split = prompt_text.split(maxsplit=1)
                    filename = (
                        parts_split[1].strip() if len(parts_split) > 1 else "kourai_output.md"
                    )
                    try:
                        await AnyioPath(filename).write_text(_last_result, encoding="utf-8")
                        _echo(f"{_GOLD_BRIGHT}\u2728 Saved to {filename}{_RESET}")
                    except Exception as e:
                        _echo(f"{_RED}Save failed: {e}{_RESET}")
                    continue

                if prompt_text == ":clear":
                    click.clear()
                    continue

                if prompt_text.startswith(":"):
                    _echo(
                        f"{_DIM}Unknown command: {prompt_text} \u2014 "
                        "type :help for available commands{_RESET}"
                    )
                    continue

                if not prompt_text:
                    continue

                # Grab any images queued via Alt+V and clear the pending list
                attachments = pending_images.copy()
                pending_images.clear()

                _echo("")
                keep_going, context_id, _ = await send_and_stream(
                    client,
                    prompt_text,
                    context_id,
                    verbose=verbose,
                    attachments=attachments or None,
                )
                _echo("")

                if not keep_going:
                    _echo(f"{_GOLD}Farewell from the forge! \u2728{_RESET}")
                    break
    finally:
        if hasattr(client, "close"):
            await client.close()  # type: ignore[attr-defined]


if __name__ == "__main__":
    asyncio.run(main())
