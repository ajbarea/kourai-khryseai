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
from pathlib import Path
from typing import Literal
from uuid import uuid4

import asyncclick as click
import httpx
from a2a.client import ClientConfig
from anyio import Path as AnyioPath
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.patch_stdout import patch_stdout

from hosts.cli.commands import _build_key_bindings, _copy_to_clipboard, _show_help, _show_settings
from hosts.cli.events import (  # noqa: F401 — re-exported for backward compat
    _extract_artifact_text,
    _extract_status_text,
)
from hosts.cli.headless import _headless
from hosts.cli.maidens import _MAIDEN_FACES, _MAIDENS
from hosts.cli.rendering import _banner, _echo, _maiden_card, _maiden_gallery, set_raw_out
from hosts.cli.settings import CLISettings
from hosts.cli.streaming import _connect_with_url_override, get_last_result, send_and_stream
from hosts.cli.styling import _DIM, _GOLD, _GOLD_BRIGHT, _ITALIC, _RED, _RESET
from hosts.gui.tts_engine import TTSEngine
from kourai_common.audio import AudioManager
from kourai_common.config import MODEL_TIER, PROVIDER, get_agent_url, get_model
from kourai_common.log import setup_logging
from kourai_common.player import PlayerProfile, get_all_affinities
from kourai_common.virtues import FORGE_VIRTUES, get_virtue_deltas, get_virtue_scores

# Windows consoles default to cp1252 — force UTF-8 so emoji and box-drawing work.
# Skip when imported under pytest — replacing streams breaks pytest's capture system.
if sys.platform == "win32" and hasattr(sys.stdout, "buffer") and "pytest" not in sys.modules:
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Save a reference to the real stdout BEFORE prompt_toolkit's patch_stdout
# can wrap it.  Dense ANSI (pixel art, true-color) gets mangled by
# prompt_toolkit's VT parser on Windows — writing to the real stdout
# bypasses that entirely.  Safe because we only _echo() between prompts,
set_raw_out(sys.stdout)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _tier_persona_name(tier: str) -> str:
    return {"cheap": "haiku", "standard": "sonnet", "smart": "opus"}.get(tier, tier)


def _active_model_label() -> str:
    model_id = get_model("hephaestus")
    return f"{PROVIDER}:{_tier_persona_name(MODEL_TIER)} ({model_id.split('/', 1)[-1]})"


def _apply_audio_settings(
    audio: AudioManager, settings: CLISettings, tts: TTSEngine | None
) -> TTSEngine | None:
    """Apply persisted audio/voice settings to runtime systems."""
    if not audio.audio_available:
        if tts:
            tts.cleanup()
        return None

    ambient = PROJECT_ROOT / "assets" / "audio" / "ambient" / "forge_loop.ogg"
    music_dir = PROJECT_ROOT / "assets" / "audio" / "music"

    if settings.ambient_enabled:
        if ambient.exists():
            audio.play_ambient(ambient)
    elif audio.ambient_channel is not None:
        audio.ambient_channel.stop()

    if settings.music_enabled:
        if music_dir.exists():
            audio.load_playlist(str(music_dir))
            audio.play_playlist()
    else:
        audio.stop_music(fade_ms=300)

    if settings.voice_enabled:
        if tts is None:
            return TTSEngine()
        return tts

    if tts is not None:
        tts.cleanup()
    return None


def _sync_profile_with_settings(settings: CLISettings) -> None:
    """Mirror runtime settings into the active player profile preferences."""
    profile = PlayerProfile.load()
    if profile is None:
        return
    profile.romance_opted_out = not settings.romance_enabled
    profile.jealousy_enabled = settings.romance_enabled
    profile.preferences["metrics_tracking_enabled"] = settings.metrics_tracking_enabled
    profile.preferences["affinity_tracking_enabled"] = settings.metrics_tracking_enabled
    profile.preferences["virtue_tracking_enabled"] = settings.metrics_tracking_enabled
    profile.preferences["gossip_enabled"] = settings.gossip_enabled
    profile.preferences["romance_nudges_enabled"] = settings.romance_nudges_enabled
    profile.preferences["gossip_nudges_enabled"] = settings.gossip_nudges_enabled
    profile.save()


def _maybe_offer_feature_opt_in(
    settings: CLISettings,
    *,
    feature: Literal["romance", "gossip"],
    turn_counter: int,
    last_nudge_turn: int,
) -> tuple[int, bool, bool]:
    """Offer progressive opt-in: enable now / not now / never ask again."""
    enabled_key = f"{feature}_enabled"
    nudge_key = f"{feature}_nudges_enabled"
    enabled = bool(getattr(settings, enabled_key))
    nudges_enabled = bool(getattr(settings, nudge_key))

    if enabled or not nudges_enabled:
        return last_nudge_turn, False, False

    if feature == "romance":
        min_turns, cooldown = 4, 8
        speaker = "Cupid"
        pitch = "I can open romance arcs in the forge. Want me to enable them now?"
    else:
        min_turns, cooldown = 3, 6
        speaker = "Puck"
        pitch = "I can spin up idle gossip while agents work. Turn it on?"

    if turn_counter < min_turns or turn_counter - last_nudge_turn < cooldown:
        return last_nudge_turn, False, False

    _echo("")
    _echo(f"{_GOLD}{speaker}:{_RESET} {_ITALIC}{pitch}{_RESET}")
    choice = input(
        f"  {_GOLD}[E]{_RESET}nable / {_GOLD}[N]{_RESET}ot now / {_GOLD}[V]{_RESET}never ask: "
    )
    choice = choice.strip().lower()[:1]

    if choice == "e":
        setattr(settings, enabled_key, True)
        settings.save()
        _echo(f"  {_DIM}{feature.title()} enabled.{_RESET}")
        return turn_counter, True, True

    if choice == "v":
        setattr(settings, nudge_key, False)
        settings.save()
        _echo(f"  {_DIM}Got it — no more {feature} nudges.{_RESET}")
        return turn_counter, True, True

    _echo(f"  {_DIM}Not now — I'll ask again later.{_RESET}")
    return turn_counter, False, True


def _format_affinity_bar(score: float, width: int = 14) -> str:
    """Render a fixed-width bar for affinity score in [-1.0, 1.0]."""
    score = max(-1.0, min(1.0, score))
    fill = int(((score + 1.0) / 2.0) * width)
    fill = max(0, min(width, fill))
    return ("█" * fill) + ("·" * (width - fill))


def _show_metrics_dashboard() -> None:
    """Display transparent player metrics: alignment, affinity, and virtues."""
    profile = PlayerProfile.load()
    if profile is None:
        _echo(f"{_DIM}No active profile yet — run onboarding first.{_RESET}")
        return

    tracking_enabled = bool(profile.preferences.get("metrics_tracking_enabled", True))
    _echo(f"\n{_GOLD_BRIGHT}━━━ Forge Metrics ━━━{_RESET}")
    _echo(
        "  "
        f"{_GOLD}Tracking:{_RESET} {'ON' if tracking_enabled else 'OFF'}"
        f"  {_DIM}({'live updates' if tracking_enabled else 'frozen history'}){_RESET}"
    )
    _echo(
        "  "
        f"{_GOLD}Alignment:{_RESET} sovereignty={profile.sovereignty}/100 · "
        f"devotion={profile.devotion}/100 · archetype={profile.archetype}"
    )

    affinities = get_all_affinities(profile.player_id)
    if affinities:
        _echo(f"\n  {_GOLD}Agent Affinity{_RESET} {_DIM}(score, interactions, stage){_RESET}")
        for agent_name, aff in sorted(
            affinities.items(), key=lambda item: item[1]["affinity_score"], reverse=True
        ):
            score = float(aff["affinity_score"])
            _echo(
                f"  - {agent_name:<10} {score:+.2f} {_DIM}[{_format_affinity_bar(score)}]{_RESET} "
                f"{_DIM}n={aff['interaction_count']} · stage={aff['romance_stage']}{_RESET}"
            )
    else:
        _echo(f"\n  {_DIM}No affinity history yet.{_RESET}")

    scores = get_virtue_scores(profile.player_id)
    deltas = get_virtue_deltas(profile.player_id)
    _echo(f"\n  {_GOLD}Forge Virtues{_RESET} {_DIM}(score with session delta){_RESET}")
    for key, virtue in FORGE_VIRTUES.items():
        score = float(scores.get(key, 0.5))
        delta = float(deltas.get(key, 0.0))
        delta_label = f"{delta:+.2f}" if delta else "—"
        _echo(f"  - {virtue.name:<10} {score:>5.2f}  {_DIM}Δ {delta_label}{_RESET}")

    _echo("")


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
@click.option(
    "--voice",
    is_flag=True,
    default=None,  # None means use saved setting
    help="Enable text-to-speech for agent dialogue (overrides saved setting)",
)
async def main(
    agent: str | None, timeout_seconds: int, verbose: bool, prompt: str | None, voice: bool | None
) -> None:
    """Interactive CLI for Kourai Khryseai agent swarm."""
    setup_logging("cli", level="DEBUG" if verbose else "INFO")
    if not agent:
        agent = get_agent_url("hephaestus")

    # Load persistent settings
    settings = CLISettings.load()
    if voice is not None:
        settings.voice_enabled = voice
    _sync_profile_with_settings(settings)

    # Initialize audio system (forge ambient + playlist)
    audio = AudioManager()
    tts: TTSEngine | None = None
    tts = _apply_audio_settings(audio, settings, tts)

    # Headless mode — run a single prompt and exit (for scripts / piping)
    if prompt:
        try:
            await _headless(agent, prompt, timeout_seconds, verbose)
        finally:
            audio.cleanup()
            if tts:
                tts.cleanup()
        return

    _echo(_banner())

    # First-run onboarding — collect player identity before connecting
    from hosts.cli.onboarding import increment_session, needs_onboarding, run_onboarding

    if needs_onboarding():
        run_onboarding()
        settings = CLISettings.load()
        _sync_profile_with_settings(settings)
        tts = _apply_audio_settings(audio, settings, tts)
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
    model_label = _active_model_label()
    _echo(f"Connected to {_GOLD}{card.name}{_RESET} v{card.version}")
    _echo(f"Skills: {_DIM}{', '.join(s.name for s in card.skills)}{_RESET}")
    _echo(f"Model: {_DIM}{model_label}{_RESET}")
    _echo(
        "Systems: "
        f"{_DIM}metrics={'ON' if settings.metrics_tracking_enabled else 'OFF'}"
        f" · romance={'ON' if settings.romance_enabled else 'OFF'}"
        f" · gossip={'ON' if settings.gossip_enabled else 'OFF'}{_RESET}"
    )
    if verbose:
        _echo(f"{_DIM}[verbose] URL={agent} streaming={card.capabilities.streaming}{_RESET}")

    # Random maiden greeting on startup — maidens flirt with the user,
    # Hephaestus is gruff but welcoming. user_quotes are the warm ones.
    _greet_name = secrets.choice(list(_MAIDENS.keys()))
    _greet_m = _MAIDENS[_greet_name]
    _greet_quotes = (
        _greet_m.get("user_quotes", _greet_m["quotes"])
        if settings.romance_enabled
        else _greet_m["quotes"]
    )
    _greet_quote = secrets.choice(_greet_quotes)
    _echo(f"\n  {_GOLD}{_MAIDEN_FACES[_greet_name]}{_RESET} {_ITALIC}{_greet_quote}{_RESET}")
    _echo("")
    if tts:
        await tts.speak(_greet_quote, _greet_name)

    context_id: str = uuid4().hex
    pending_images: list[tuple[str, str]] = []  # (base64_bytes, mime_type)
    kb = _build_key_bindings(pending_images)
    session: PromptSession[str] = PromptSession(key_bindings=kb, multiline=False)

    def _toolbar() -> str:
        img = f"  \U0001f4ce {len(pending_images)} image(s) queued" if pending_images else ""
        return (
            f"{PROVIDER}:{_tier_persona_name(MODEL_TIER)}"
            "  ·  Enter send  ·  Alt+V attach image  ·  /help  ·  :q quit"
            f"{img}"
        )

    turn_counter = 0
    last_romance_nudge_turn = -999
    last_gossip_nudge_turn = -999

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
                if prompt_text in (":help", "/help"):
                    _show_help()
                    continue

                if prompt_text in (":settings", "/settings", ":config", "/config"):
                    _show_settings()
                    settings = CLISettings.load()
                    _sync_profile_with_settings(settings)
                    tts = _apply_audio_settings(audio, settings, tts)
                    _echo(
                        f"{_DIM}Updated systems: metrics={'ON' if settings.metrics_tracking_enabled else 'OFF'} "
                        f"· romance={'ON' if settings.romance_enabled else 'OFF'} "
                        f"· gossip={'ON' if settings.gossip_enabled else 'OFF'}{_RESET}"
                    )
                    continue

                if prompt_text in (":model_tier", "/model_tier"):
                    _echo(f"  {_GOLD}Provider:{_RESET}  {PROVIDER}")
                    _echo(
                        f"  {_GOLD}Tier:{_RESET}      {MODEL_TIER} ({_tier_persona_name(MODEL_TIER)})"
                    )
                    _echo(f"  {_GOLD}Model:{_RESET}     {get_model('hephaestus')}")
                    continue

                if prompt_text in (":metrics", "/metrics"):
                    _show_metrics_dashboard()
                    continue

                if prompt_text.startswith((":maidens", "/maidens")):
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

                if prompt_text in (":status", "/status"):
                    _echo(f"  {_GOLD}Agent:{_RESET}     {card.name} v{card.version}")
                    _echo(f"  {_GOLD}URL:{_RESET}       {agent}")
                    _echo(f"  {_GOLD}Model:{_RESET}     {model_label}")
                    _echo(f"  {_GOLD}Context:{_RESET}   {context_id}")
                    _echo(f"  {_GOLD}Streaming:{_RESET} {card.capabilities.streaming}")
                    _echo(
                        f"  {_GOLD}Systems:{_RESET}   metrics={'ON' if settings.metrics_tracking_enabled else 'OFF'} "
                        f"· romance={'ON' if settings.romance_enabled else 'OFF'} "
                        f"· gossip={'ON' if settings.gossip_enabled else 'OFF'}"
                    )
                    continue

                if prompt_text in (":copy", "/copy"):
                    _last_result = get_last_result()
                    if not _last_result:
                        _echo(f"{_DIM}Nothing to copy yet \u2014 run a command first.{_RESET}")
                    elif _copy_to_clipboard(_last_result):
                        _echo(f"{_GOLD_BRIGHT}\u2728 Copied to clipboard!{_RESET}")
                    else:
                        _echo(f"{_RED}Clipboard copy failed \u2014 try :save instead{_RESET}")
                    continue

                if prompt_text.startswith((":save", "/save")):
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

                if prompt_text in (":clear", "/clear"):
                    click.clear()
                    continue

                if prompt_text.startswith((":", "/")):
                    _echo(
                        f"{_DIM}Unknown command: {prompt_text} \u2014 "
                        "type /help for available commands{_RESET}"
                    )
                    continue

                if not prompt_text:
                    continue

                # Grab any images queued via Alt+V and clear the pending list
                attachments = pending_images.copy()
                pending_images.clear()
                turn_counter += 1

                _echo("")
                keep_going, context_id, _ = await send_and_stream(
                    client,
                    prompt_text,
                    context_id,
                    verbose=verbose,
                    attachments=attachments or None,
                    tts=tts,
                    gossip_enabled=settings.gossip_enabled,
                )

                # Progressive, reversible opt-ins for game mechanics.
                last_romance_nudge_turn, changed, prompted = _maybe_offer_feature_opt_in(
                    settings,
                    feature="romance",
                    turn_counter=turn_counter,
                    last_nudge_turn=last_romance_nudge_turn,
                )
                if changed:
                    _sync_profile_with_settings(settings)
                    tts = _apply_audio_settings(audio, settings, tts)

                if not prompted:
                    last_gossip_nudge_turn, changed, _ = _maybe_offer_feature_opt_in(
                        settings,
                        feature="gossip",
                        turn_counter=turn_counter,
                        last_nudge_turn=last_gossip_nudge_turn,
                    )
                    if changed:
                        _sync_profile_with_settings(settings)
                        tts = _apply_audio_settings(audio, settings, tts)
                _echo("")

                if not keep_going:
                    _echo(f"{_GOLD}Farewell from the forge! \u2728{_RESET}")
                    break
    finally:
        audio.cleanup()
        if tts:
            tts.cleanup()
        if hasattr(client, "close"):
            await client.close()  # type: ignore[attr-defined]


if __name__ == "__main__":
    asyncio.run(main())
