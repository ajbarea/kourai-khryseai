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
from prompt_toolkit.styles import Style

from hosts.cli.commands import (
    _active_project,
    _build_key_bindings,
    _copy_to_clipboard,
    _handle_project_command,
    _show_help,
    _show_settings,
)
from hosts.cli.completer import SlashCommandCompleter
from hosts.cli.demo import run_demo
from hosts.cli.headless import _headless
from hosts.cli.maidens import _MAIDEN_FACES, _MAIDENS
from hosts.cli.rendering import (
    _banner,
    _clear_screen,
    _echo,
    _maiden_card,
    _maiden_gallery,
    set_raw_out,
)
from hosts.cli.settings import CLISettings
from hosts.cli.streaming import _connect_with_url_override, get_last_result, send_and_stream
from hosts.cli.styling import _DIM, _GOLD, _GOLD_BRIGHT, _ITALIC, _RED, _RESET
from hosts.gui.tts_engine import TTSEngine
from kourai_common.audio import AudioManager
from kourai_common.config import MODEL_TIER, PROVIDER, get_agent_url, get_model
from kourai_common.federation.host_helpers import derive_scene_id
from kourai_common.federation.memoir import Memoir
from kourai_common.forge_session import ForgeSession, ForgeSessionError
from kourai_common.log import setup_logging
from kourai_common.player import PlayerProfile, get_all_affinities
from kourai_common.virtues import FORGE_VIRTUES, get_virtue_deltas, get_virtue_scores

_COMPLETER_STYLE = Style.from_dict(
    {
        "completion-menu.completion": "bg:#1a1a1a #d7af00",
        "completion-menu.completion.current": "bg:#d7af00 #000000 bold",
        "completion-menu.meta.completion": "bg:#1a1a1a #888888",
        "completion-menu.meta.completion.current": "bg:#d7af00 #1a1a1a",
        "scrollbar.background": "bg:#1a1a1a",
        "scrollbar.button": "bg:#888888",
        "slash-cmd": "#d7af00 bold",
        "slash-arg-hint": "#888888 italic",
    }
)

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


def _show_usage_summary() -> None:
    """Print per-agent / per-model token totals + dollar cost for the session.

    Pulls from kourai_common.usage's session accumulator (populated by
    record_usage hooks in chat() and chat_with_tools()). Buckets are
    keyed on (agent_name, model) so M14's cheap-tier override is
    visible as a separate row from Metis's smart-tier spec spend
    rather than the second one masking the first. Streaming calls via
    chat_stream() are not currently captured — final-chunk usage
    isn't surfaced through LiteLLM's iterator interface today.
    """
    from kourai_common.pricing import compute_cost
    from kourai_common.usage import get_session_usage

    snapshot = get_session_usage()
    if not snapshot.agents:
        _echo(f"{_DIM}No usage recorded yet — issue a request first.{_RESET}")
        return

    _echo(f"\n{_GOLD_BRIGHT}━━━ Session Usage ━━━{_RESET}")
    _echo(
        f"  {_DIM}{'agent':<11} {'tier':<8} {'calls':>5} {'in':>10} {'out':>9} "
        f"{'cache_r':>9} {'cache_w':>9} {'cost':>10}{_RESET}"
    )

    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cache_write = 0
    total_cost = 0.0
    unknown_models: set[str] = set()

    # Sort by (agent_name, model) so multi-model agents render in a
    # stable order — same agent name groups visually.
    for key in sorted(snapshot.agents):
        agent_name, model = key
        u = snapshot.agents[key]
        cost = compute_cost(u.model, u) if u.model else None
        cost_str = f"${cost:>8.4f}" if cost is not None else f"{_DIM}    $—   {_RESET}"
        if cost is None and u.model:
            unknown_models.add(u.model)
        if cost is not None:
            total_cost += cost
        # Show just the model's short name, not the full provider path,
        # so the row stays narrow. "anthropic/claude-haiku-4-5-20251001"
        # → "haiku-4-5".
        tier_label = _short_model_label(model)
        _echo(
            f"  {_GOLD}{agent_name:<11}{_RESET} {_DIM}{tier_label:<8}{_RESET} "
            f"{u.calls:>5} {u.input_tokens:>10,} {u.output_tokens:>9,} "
            f"{u.cache_read_tokens:>9,} {u.cache_write_tokens:>9,} {cost_str}"
        )
        total_input += u.input_tokens
        total_output += u.output_tokens
        total_cache_read += u.cache_read_tokens
        total_cache_write += u.cache_write_tokens

    _echo(
        f"  {_DIM}{'─' * 80}{_RESET}\n"
        f"  {_GOLD}{'TOTAL':<11}{_RESET}          {total_input:>10,} "
        f"{total_output:>9,} {total_cache_read:>9,} "
        f"{total_cache_write:>9,} {_GOLD}${total_cost:>8.4f}{_RESET}"
    )

    if unknown_models:
        _echo(
            f"  {_DIM}(no pricing for: {', '.join(sorted(unknown_models))} "
            f"— add to kourai_common.pricing.ANTHROPIC_PRICING){_RESET}"
        )


def _short_model_label(model: str) -> str:
    """Compress a model id to a column-friendly label.

    ``anthropic/claude-haiku-4-5-20251001`` → ``haiku-4-5``.
    ``anthropic/claude-sonnet-4-6`` → ``sonnet``.
    ``anthropic/claude-opus-4-7`` → ``opus``.
    ``gemini/gemini-2.5-pro`` → ``2.5-pro``.

    Empty / unrecognised input returns ``"?"`` so the column never
    overflows.
    """
    if not model:
        return "?"
    short = model.split("/", 1)[-1]
    short = short.replace("claude-", "")
    # Trim to fit the 8-char column without truncating mid-word.
    if "-" in short:
        head, sep, _ = short.partition("-")
        # Single-segment model names ("opus", "sonnet") keep as-is;
        # versioned ones keep head + first segment ("haiku-4-5").
        if head in ("haiku", "sonnet", "opus"):
            # Pull "haiku-4-5" out of "haiku-4-5-20251001".
            chunks = short.split("-")
            return "-".join(chunks[:3]) if len(chunks) >= 3 else short
    return short[:8]


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
@click.option(
    "--demo",
    "demo_mode",
    is_flag=True,
    default=False,
    help="Play a scripted Hephaestus→Metis pause scene without touching the network "
    "(for poster screenshots and recordings).",
)
async def main(
    agent: str | None,
    timeout_seconds: int,
    verbose: bool,
    prompt: str | None,
    voice: bool | None,
    demo_mode: bool,
) -> None:
    """Interactive CLI for Kourai Khryseai agent swarm."""
    setup_logging("cli", level="DEBUG" if verbose else "INFO")

    # Demo mode — scripted pipeline, no network, no LLM. Exits after the
    # user responds to the Metis clarification prompt (or Ctrl-C).
    if demo_mode:
        await run_demo(prompt)
        return

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
    # Only consider maidens that actually have a non-empty quote pool for the
    # active romance setting (puck/cupid have no quotes and would crash choice).
    def _has_quotes(m: dict) -> bool:
        pool = m.get("user_quotes") if settings.romance_enabled else m.get("quotes")
        if pool:
            return True
        return bool(m.get("quotes"))

    _greet_candidates = [n for n, m in _MAIDENS.items() if _has_quotes(m)]
    _greet_name = secrets.choice(_greet_candidates)
    _greet_m = _MAIDENS[_greet_name]
    _greet_quotes = (
        _greet_m.get("user_quotes") or _greet_m["quotes"]
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
    session: PromptSession[str] = PromptSession(
        key_bindings=kb,
        multiline=False,
        completer=SlashCommandCompleter(),
        complete_while_typing=True,
        enable_history_search=False,
        style=_COMPLETER_STYLE,
    )

    def _toolbar() -> str:
        img = f"  \U0001f4ce {len(pending_images)} image(s) queued" if pending_images else ""
        return (
            f"{PROVIDER}:{_tier_persona_name(MODEL_TIER)}"
            "  ·  Enter send  ·  Alt+V attach image  ·  /help  ·  /q quit"
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

                if prompt_text.lower() in ("/q", "/quit", "/exit", "quit", "exit"):
                    _echo(f"{_GOLD}Farewell from the forge! \u2728{_RESET}")
                    break

                # --- Command dispatch ---
                if prompt_text == "/help":
                    _show_help()
                    continue

                if (
                    prompt_text == "/settings"
                    or prompt_text == "/config"
                    or prompt_text.startswith(("/settings ", "/config "))
                ):
                    head, _, arg = prompt_text.partition(" ")
                    _show_settings(arg.strip() or None)
                    settings = CLISettings.load()
                    _sync_profile_with_settings(settings)
                    tts = _apply_audio_settings(audio, settings, tts)
                    _echo(
                        f"{_DIM}Updated systems: metrics={'ON' if settings.metrics_tracking_enabled else 'OFF'} "
                        f"· romance={'ON' if settings.romance_enabled else 'OFF'} "
                        f"· gossip={'ON' if settings.gossip_enabled else 'OFF'}{_RESET}"
                    )
                    continue

                if prompt_text == "/model_tier":
                    _echo(f"  {_GOLD}Provider:{_RESET}  {PROVIDER}")
                    _echo(
                        f"  {_GOLD}Tier:{_RESET}      {MODEL_TIER} ({_tier_persona_name(MODEL_TIER)})"
                    )
                    _echo(f"  {_GOLD}Model:{_RESET}     {get_model('hephaestus')}")
                    continue

                if prompt_text == "/usage":
                    _show_usage_summary()
                    continue

                if prompt_text == "/reset_usage":
                    from kourai_common.usage import reset_session_usage

                    reset_session_usage()
                    _echo(f"  {_DIM}Session usage cleared.{_RESET}")
                    continue

                if prompt_text == "/yolo":
                    settings.yolo_enabled = not settings.yolo_enabled
                    settings.save()
                    state = "ON" if settings.yolo_enabled else "OFF"
                    desc = (
                        "bypassed — pipelines run without read-back"
                        if settings.yolo_enabled
                        else "active — Hephaestus reads back before any pipeline"
                    )
                    _echo(f"  {_GOLD}/yolo{_RESET} {state} — confirmation gate {desc}.")
                    continue

                if prompt_text == "/metrics":
                    _show_metrics_dashboard()
                    continue

                if prompt_text.startswith("/maidens"):
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

                if prompt_text == "/status":
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

                if prompt_text.startswith("/project"):
                    _handle_project_command(prompt_text.lstrip("/"), settings)
                    continue

                if prompt_text == "/copy":
                    _last_result = get_last_result()
                    if not _last_result:
                        _echo(f"{_DIM}Nothing to copy yet \u2014 run a command first.{_RESET}")
                    elif _copy_to_clipboard(_last_result):
                        _echo(f"{_GOLD_BRIGHT}\u2728 Copied to clipboard!{_RESET}")
                    else:
                        _echo(f"{_RED}Clipboard copy failed \u2014 try /save instead{_RESET}")
                    continue

                if prompt_text.startswith("/save"):
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

                if prompt_text == "/clear":
                    _clear_screen()
                    continue

                if prompt_text.startswith("/"):
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

                # If a project is selected, wrap this turn in a forge worktree
                # session and inject the worktree path as the project_root so
                # specialists run there instead of the kourai source tree.
                forge_msg = prompt_text
                forge_session: ForgeSession | None = None
                forge_memoir: Memoir | None = None
                forge_turn_number: int = 0
                project = _active_project(settings)
                if project is not None:
                    try:
                        forge_session = ForgeSession.start(project, label=prompt_text[:24])
                        forge_memoir = Memoir(forge_session.workdir)
                        forge_turn_number = 0
                        forge_msg = f"[project_root: {forge_session.workdir}]\n{prompt_text}"
                        _echo(
                            f"{_DIM}\u2692 Forging in {project.name}"
                            f" \u00b7 session {forge_session.session_id[:8]}"
                            f" \u00b7 branch {forge_session.branch}{_RESET}"
                        )
                    except ForgeSessionError as exc:
                        _echo(
                            f"{_RED}Could not start forge session: {exc}"
                            f" \u2014 falling back to no-project mode.{_RESET}"
                        )

                # M13 yolo bypass — when on, prepend a tag the Hephaestus
                # router strips and treats as "skip CONFIRM_ORDER, route
                # straight to the agent list". Same text-tag convention as
                # [project_root: …] and [relationship_tiers: …]. Default OFF
                # so the gate stays the contract of the forge.
                if settings.yolo_enabled:
                    forge_msg = f"[yolo: on]\n{forge_msg}"

                _echo("")
                stream_kwargs: dict[str, object] = {}
                if forge_session is not None and forge_memoir is not None:
                    forge_turn_number += 1
                    stream_kwargs["memoir"] = forge_memoir
                    stream_kwargs["scene_id"] = derive_scene_id(
                        forge_session.session_id,
                        turn_number=forge_turn_number,
                    )
                keep_going, context_id, _ = await send_and_stream(
                    client,
                    forge_msg,
                    context_id,
                    verbose=verbose,
                    attachments=attachments or None,
                    tts=tts,
                    gossip_enabled=settings.gossip_enabled,
                    **stream_kwargs,
                )

                if forge_session is not None:
                    _echo(
                        f"{_DIM}Session {forge_session.session_id[:8]} pending. "
                        f"Resolve with /project accept {forge_session.session_id[:8]} "
                        f"or /project discard {forge_session.session_id[:8]}.{_RESET}"
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
