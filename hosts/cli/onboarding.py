"""CLI first-run onboarding — collects player identity on first launch.

Guides the player through name entry, pronunciation tuning, title/role
selection, and pronoun preferences. Saves to PlayerProfile JSON.

Role / pronoun / experience choices come from
``kourai_common.onboarding_data`` so CLI / GUI / VN agree on the
canonical option set; CLI-only metrics options stay defined locally.
"""

from __future__ import annotations

import logging

from hosts.cli.settings import CLISettings
from hosts.cli.styling import _BOLD, _CYAN, _DIM, _GOLD, _GOLD_BRIGHT, _ITALIC, _RESET
from kourai_common.onboarding_data import (
    EXPERIENCE_OPTIONS,
    PRONOUN_OPTIONS,
    ROLE_OPTIONS,
    OnboardingChoice,
)
from kourai_common.player import PlayerProfile, set_active_profile

logger = logging.getLogger(__name__)

# CLI-only — neither host duplicates these, so the canonical surface stays
# here. Same OnboardingChoice schema as the shared lists for a uniform
# render path.
METRICS_OPTIONS_FOCUSED: list[OnboardingChoice] = [
    OnboardingChoice(id="off", label="No", description="No (recommended for Focused mode)"),
    OnboardingChoice(id="on", label="Yes", description="Yes, enable affinity + virtue tracking"),
]

METRICS_OPTIONS_GAMIFIED: list[OnboardingChoice] = [
    OnboardingChoice(id="on", label="Yes", description="Yes (recommended for Gamified mode)"),
    OnboardingChoice(id="off", label="No", description="No, keep this session private"),
]


def _echo(text: str = "") -> None:
    logger.info(text)


def _input(prompt_text: str) -> str:
    try:
        return input(prompt_text).strip()
    except (EOFError, KeyboardInterrupt):
        _echo(f"\n{_DIM}Onboarding cancelled.{_RESET}")
        return ""


def _pick(options: list[OnboardingChoice], prompt_text: str) -> str:
    """Present numbered choices and return the selected ``id``."""
    _echo(prompt_text)
    for i, choice in enumerate(options, 1):
        _echo(f"  {_GOLD}{i}{_RESET}) {choice.description}")
    _echo("")

    while True:
        picked = _input(f"  {_GOLD}>{_RESET} ")
        if not picked:
            return options[0].id  # Default to first option
        try:
            idx = int(picked) - 1
            if 0 <= idx < len(options):
                return options[idx].id
        except ValueError:
            pass
        _echo(f"  {_DIM}Pick a number 1–{len(options)}{_RESET}")


def _puck_handoff_line(role: str) -> str:
    """Role-sensitive Puck handoff line before meeting Hephaestus.

    Keeps legacy CLI role IDs (``master`` / ``casual``) in the match set
    so existing player profiles routed through the CLI before the May
    2026 onboarding canonicalization still get a tonally-correct line.
    Maps to the canonical 5-role set: divine / hero / devoted (formal)
    vs mortal / name_only / casual / master (warm).
    """
    if role in {"divine", "hero", "master", "devoted"}:
        return "All right, highness — try not to smirk when the old king sizes you up."
    if role in {"mortal", "casual", "name_only"}:
        return "Stay close. Hephaestus is intense, but he respects honest craft."
    return "Easy now — first impressions matter with the Forge King."


def needs_onboarding() -> bool:
    """Check if the player has never been onboarded."""
    profile = PlayerProfile.load()
    return profile is None or not profile.display_name


def run_onboarding() -> PlayerProfile:
    """Run the interactive first-run onboarding flow.

    Returns:
        The created PlayerProfile (already saved to disk).
    """
    _echo("")
    _echo(f"  {_GOLD_BRIGHT}╔══════════════════════════════════════╗{_RESET}")
    _echo(f"  {_GOLD_BRIGHT}║   ✨ Welcome to Kourai Khryseai ✨   ║{_RESET}")
    _echo(f"  {_GOLD_BRIGHT}╚══════════════════════════════════════╝{_RESET}")
    _echo("")
    _echo(
        f'  {_CYAN}Puck:{_RESET} {_ITALIC}"Come on, I\'ll guide you to Hephaestus. The forge is waiting."{_RESET}'
    )
    _echo("")
    _echo(f"  {_BOLD}Choose your session style:{_RESET}")
    experience_mode = _pick(EXPERIENCE_OPTIONS, "")
    _echo("")
    metrics_choice = _pick(
        METRICS_OPTIONS_GAMIFIED if experience_mode == "gamified" else METRICS_OPTIONS_FOCUSED,
        f"  {_BOLD}Enable transparent gameplay metrics (affinity / virtues)?{_RESET}",
    )
    metrics_enabled = metrics_choice == "on"
    _echo("")

    _echo(f"  {_ITALIC}The Golden Maidens wish to know their new commander.{_RESET}")
    _echo("")

    # Step 1: Name
    _echo(f"  {_BOLD}What shall the maidens call you?{_RESET}")
    display_name = _input(f"  {_GOLD}Name>{_RESET} ")
    if not display_name:
        display_name = "Commander"

    # Step 2: Pronunciation
    _echo("")
    _echo(f"  {_DIM}The maidens will speak your name aloud via TTS.{_RESET}")
    _echo(f"  {_DIM}If your name has an unusual pronunciation, type how it SOUNDS.{_RESET}")
    _echo(f"  {_DIM}(e.g., 'Xiaoming' → 'Shao Ming', 'AJ' → 'ay jay'){_RESET}")
    _echo(f"  {_DIM}Press Enter to keep '{display_name}' as-is.{_RESET}")
    tts_name = _input(f"  {_GOLD}Sounds like>{_RESET} ")
    if not tts_name:
        tts_name = display_name

    # Character creator is only shown for gamified mode.
    if experience_mode == "gamified":
        _echo("")
        _echo(f"  {_BOLD}Choose a title (shown before your name in dialogue):{_RESET}")
        title = _input(f"  {_GOLD}Title>{_RESET} ")
        if not title:
            title = ""
        _echo("")

        role = _pick(
            ROLE_OPTIONS,
            f"  {_BOLD}How should the maidens address you?{_RESET}",
        )

        _echo("")
        pronouns = _pick(
            PRONOUN_OPTIONS,
            f"  {_BOLD}Pronouns (for dialogue)?{_RESET}",
        )
    else:
        title = ""
        role = "mortal"
        pronouns = ""

    _echo("")
    _echo(f'  {_CYAN}Puck:{_RESET} {_ITALIC}"{_puck_handoff_line(role)}"{_RESET}')

    # Create and save profile
    profile = PlayerProfile(
        display_name=display_name,
        tts_name=tts_name,
        title=title,
        role=role,
        pronouns=pronouns,
    )
    profile.preferences["experience_mode"] = experience_mode
    profile.preferences["metrics_tracking_enabled"] = metrics_enabled
    profile.preferences["affinity_tracking_enabled"] = metrics_enabled
    profile.preferences["virtue_tracking_enabled"] = metrics_enabled
    profile.preferences["romance_nudges_enabled"] = True
    profile.preferences["gossip_nudges_enabled"] = True
    # Romance is off by default in CLI; can be enabled later from settings.
    profile.romance_opted_out = True
    profile.jealousy_enabled = False
    profile.total_sessions = 1
    profile.save()
    set_active_profile(profile.player_id)

    # Sync first-run CLI systems defaults.
    settings = CLISettings.load()
    settings.romance_enabled = False
    settings.gossip_enabled = False
    settings.metrics_tracking_enabled = metrics_enabled
    settings.romance_nudges_enabled = True
    settings.gossip_nudges_enabled = True
    settings.save()

    # Personalized welcome
    _echo("")
    name_display = display_name
    if title:
        name_display = f"{display_name}, {title}"
    _echo(f"  {_GOLD}⚒️  Hephaestus:{_RESET} {_ITALIC}\"Ah... so you're {name_display}.{_RESET}")
    _echo(f'  {_ITALIC}  The forge has been waiting for someone like you."{_RESET}')
    _echo(
        f"  {_DIM}Mode={experience_mode} · metrics={'ON' if metrics_enabled else 'OFF'} · romance=OFF · gossip=OFF{_RESET}"
    )
    _echo("")

    return profile


def increment_session() -> None:
    """Increment session count for returning players."""
    profile = PlayerProfile.load()
    if profile:
        profile.total_sessions += 1
        profile.save()
