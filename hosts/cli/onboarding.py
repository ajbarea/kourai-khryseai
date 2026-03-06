"""CLI first-run onboarding — collects player identity on first launch.

Guides the player through name entry, pronunciation tuning, title/role
selection, and pronoun preferences. Saves to PlayerProfile JSON.
"""

from __future__ import annotations

import sys

from kourai_common.player import PlayerProfile, set_active_profile

# Reuse CLI color palette
_GOLD = "\033[38;2;218;165;32m"
_GOLD_BRIGHT = "\033[38;2;255;215;0m"
_CYAN = "\033[1;36m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_ITALIC = "\033[3m"
_RESET = "\033[0m"

# Title/role presets
ROLE_OPTIONS = [
    ("divine", "A God among mortals — the maidens serve with awe"),
    ("mortal", "A fellow artisan — the maidens treat you as an equal"),
    ("master", "Their beloved master — devoted, formal address"),
    ("casual", "Just by name — natural, relaxed conversation"),
]

PRONOUN_OPTIONS = [
    ("he/him", "he/him"),
    ("she/her", "she/her"),
    ("they/them", "they/them"),
    ("", "skip / prefer not to say"),
]


def _echo(text: str = "") -> None:
    print(text, file=sys.stdout, flush=True)


def _input(prompt_text: str) -> str:
    try:
        return input(prompt_text).strip()
    except (EOFError, KeyboardInterrupt):
        _echo(f"\n{_DIM}Onboarding cancelled.{_RESET}")
        return ""


def _pick(options: list[tuple[str, str]], prompt_text: str) -> str:
    """Present numbered options and return the selected value."""
    _echo(prompt_text)
    for i, (_, label) in enumerate(options, 1):
        _echo(f"  {_GOLD}{i}{_RESET}) {label}")
    _echo("")

    while True:
        choice = _input(f"  {_GOLD}>{_RESET} ")
        if not choice:
            return options[0][0]  # Default to first option
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx][0]
        except ValueError:
            pass
        _echo(f"  {_DIM}Pick a number 1–{len(options)}{_RESET}")


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

    # Step 3: Title
    _echo("")
    _echo(f"  {_BOLD}Choose a title (shown before your name in dialogue):{_RESET}")
    title = _input(f"  {_GOLD}Title>{_RESET} ")
    if not title:
        title = ""
    _echo("")

    # Step 4: Role / address style
    role = _pick(
        ROLE_OPTIONS,
        f"  {_BOLD}How should the maidens address you?{_RESET}",
    )

    # Step 5: Pronouns
    _echo("")
    pronouns = _pick(
        PRONOUN_OPTIONS,
        f"  {_BOLD}Pronouns (for dialogue)?{_RESET}",
    )

    # Create and save profile
    profile = PlayerProfile(
        display_name=display_name,
        tts_name=tts_name,
        title=title,
        role=role,
        pronouns=pronouns,
    )
    profile.total_sessions = 1
    profile.save()
    set_active_profile(profile.player_id)

    # Personalized welcome
    _echo("")
    name_display = display_name
    if title:
        name_display = f"{display_name}, {title}"
    _echo(f"  {_GOLD}⚒️  Hephaestus:{_RESET} {_ITALIC}\"Ah... so you're {name_display}.{_RESET}")
    _echo(f'  {_ITALIC}  The forge has been waiting for someone like you."{_RESET}')
    _echo("")

    return profile


def increment_session() -> None:
    """Increment session count for returning players."""
    profile = PlayerProfile.load()
    if profile:
        profile.total_sessions += 1
        profile.save()
