"""Player profile dataclass and multi-profile management.

Split from player.py for focused responsibility. Handles identity, alignment
gauges, serialization, and profile lifecycle (create/load/save/switch/delete).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from kourai_common.player_constants import (
    _LEGACY_PLAYER_FILE,
    ACTIVE_PROFILE_FILE,
    AGENT_ALIGNMENT_PREFERENCES,
    ALIGNMENT_COMMANDER,
    ALIGNMENT_HIGH,
    PLAYER_DIR,
    PROFILES_DIR,
    _now_iso,
)

log = logging.getLogger(__name__)


# ── Player Profile ──────────────────────────────────────────────────────


@dataclass
class PlayerProfile:
    """Persistent player identity and alignment state."""

    player_id: str = ""
    display_name: str = ""
    tts_name: str = ""  # Phonetic respelling for TTS pronunciation
    title: str = ""  # e.g., "The Architect"
    role: str = "mortal"  # "divine" | "mortal" | "custom"
    pronouns: str = ""  # "he/him", "she/her", "they/them", ""

    # Alignment gauges (0–100 each, independent like ME2 Paragon/Renegade)
    sovereignty: int = 0  # Red gauge: authority, perfectionism, command
    devotion: int = 0  # Blue gauge: warmth, trust, encouragement

    # Romance tracking
    romance_targets: list[str] = field(default_factory=list)
    romance_opted_out: bool = False
    jealousy_enabled: bool = True

    # Session tracking
    created_at: str = ""
    last_seen: str = ""
    total_sessions: int = 0

    # Extensible preferences bucket
    preferences: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.player_id:
            self.player_id = uuid4().hex
        if not self.created_at:
            self.created_at = _now_iso()

    # ── Alignment helpers ────────────────────────────────────────────

    @property
    def archetype(self) -> str:
        """Current alignment archetype based on gauge levels."""
        high_sov = self.sovereignty >= ALIGNMENT_HIGH
        high_dev = self.devotion >= ALIGNMENT_HIGH
        if high_sov and high_dev:
            return "commander"
        if high_sov:
            return "tyrant"
        if high_dev:
            return "patron"
        return "professional"

    @property
    def is_commander(self) -> bool:
        return self.sovereignty >= ALIGNMENT_COMMANDER and self.devotion >= ALIGNMENT_COMMANDER

    def add_sovereignty(self, points: int) -> None:
        """Award sovereignty points (clamped 0–100)."""
        self.sovereignty = min(100, max(0, self.sovereignty + points))

    def add_devotion(self, points: int) -> None:
        """Award devotion points (clamped 0–100)."""
        self.devotion = min(100, max(0, self.devotion + points))

    def alignment_compatibility(self, agent_name: str) -> float:
        """Compute alignment compatibility multiplier for an agent (0.5–1.5).

        High compatibility means the player's alignment matches what the agent
        prefers, boosting affinity gain by up to 1.5x. Low compatibility
        reduces it to 0.5x minimum.
        """
        prefs = AGENT_ALIGNMENT_PREFERENCES.get(agent_name)
        if not prefs:
            return 1.0

        # Normalize gauges to 0–1
        sov_norm = self.sovereignty / 100.0
        dev_norm = self.devotion / 100.0

        # Weighted dot product: how well player alignment matches agent preference
        score = (sov_norm * prefs["sovereignty"]) + (dev_norm * prefs["devotion"])

        # Map from roughly [-1, 1] range to [0.5, 1.5] multiplier
        return max(0.5, min(1.5, 1.0 + score * 0.5))

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlayerProfile:
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def save(self) -> None:
        """Persist profile to ~/.kourai_khryseai/profiles/{player_id}.json."""
        self.last_seen = _now_iso()
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        profile_path = PROFILES_DIR / f"{self.player_id}.json"
        try:
            profile_path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        except OSError as e:
            log.warning("Failed to save player profile: %s", e)

    @classmethod
    def load(cls, player_id: str | None = None) -> PlayerProfile | None:
        """Load a profile from disk.

        Args:
            player_id: Specific profile ID to load. If None, loads the active profile.

        Returns:
            The loaded profile, or None if not found.
        """
        if player_id:
            return cls._load_by_id(player_id)

        # Load active profile
        active_id = get_active_profile_id()
        if active_id:
            profile = cls._load_by_id(active_id)
            if profile:
                return profile

        # Migration: check legacy single-file location
        if _LEGACY_PLAYER_FILE.exists():
            try:
                data = json.loads(_LEGACY_PLAYER_FILE.read_text(encoding="utf-8"))
                profile = cls.from_dict(data)
                # Migrate to multi-profile storage
                profile.save()
                set_active_profile(profile.player_id)
                _LEGACY_PLAYER_FILE.rename(_LEGACY_PLAYER_FILE.with_suffix(".json.migrated"))
                log.info("Migrated legacy profile to multi-profile storage")
                return profile
            except (OSError, json.JSONDecodeError) as e:
                log.warning("Failed to migrate legacy profile: %s", e)

        # Fallback: if exactly one profile exists, use it and set as active
        if PROFILES_DIR.exists():
            profile_files = list(PROFILES_DIR.glob("*.json"))
            if len(profile_files) == 1:
                try:
                    data = json.loads(profile_files[0].read_text(encoding="utf-8"))
                    profile = cls.from_dict(data)
                    set_active_profile(profile.player_id)
                    return profile
                except (OSError, json.JSONDecodeError):
                    pass

        return None

    @classmethod
    def _load_by_id(cls, player_id: str) -> PlayerProfile | None:
        """Load a specific profile by ID."""
        profile_path = PROFILES_DIR / f"{player_id}.json"
        if not profile_path.exists():
            return None
        try:
            data = json.loads(profile_path.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except (OSError, json.JSONDecodeError) as e:
            log.warning("Failed to load profile %s: %s", player_id[:8], e)
            return None

    @classmethod
    def load_or_default(cls) -> PlayerProfile:
        """Load active profile or return a blank one."""
        return cls.load() or cls()


# ── Multi-Profile Management ────────────────────────────────────────────


def get_active_profile_id() -> str | None:
    """Get the ID of the currently active profile, or None."""
    if not ACTIVE_PROFILE_FILE.exists():
        return None
    try:
        pid = ACTIVE_PROFILE_FILE.read_text(encoding="utf-8").strip()
        return pid or None
    except OSError:
        return None


def set_active_profile(player_id: str) -> None:
    """Set the active profile by ID."""
    PLAYER_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_PROFILE_FILE.write_text(player_id, encoding="utf-8")


def list_profiles() -> list[dict[str, Any]]:
    """List all saved profiles with summary info.

    Returns:
        List of dicts with: player_id, display_name, role, sovereignty,
        devotion, total_sessions, last_seen, is_active.
    """
    if not PROFILES_DIR.exists():
        return []

    active_id = get_active_profile_id()
    profiles = []

    for path in sorted(PROFILES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            profiles.append(
                {
                    "player_id": data.get("player_id", path.stem),
                    "display_name": data.get("display_name", "Unknown"),
                    "role": data.get("role", "mortal"),
                    "title": data.get("title", ""),
                    "pronouns": data.get("pronouns", ""),
                    "sovereignty": data.get("sovereignty", 0),
                    "devotion": data.get("devotion", 0),
                    "total_sessions": data.get("total_sessions", 0),
                    "last_seen": data.get("last_seen", ""),
                    "created_at": data.get("created_at", ""),
                    "is_active": data.get("player_id", path.stem) == active_id,
                }
            )
        except (OSError, json.JSONDecodeError):
            continue

    return profiles


def switch_profile(player_id: str) -> PlayerProfile | None:
    """Switch to a different profile. Returns the loaded profile or None."""
    profile = PlayerProfile.load(player_id)
    if profile:
        set_active_profile(player_id)
        log.info("Switched to profile: %s (%s)", profile.display_name, player_id[:8])
    return profile


def delete_profile(player_id: str) -> bool:
    """Delete a profile and its data. Returns True if deleted."""
    # Lazy import to avoid circular dependency
    from kourai_common.player_memory import wipe_player_memories

    profile_path = PROFILES_DIR / f"{player_id}.json"
    if not profile_path.exists():
        return False

    try:
        profile_path.unlink()
        # Clear active pointer if this was the active profile
        if get_active_profile_id() == player_id:
            ACTIVE_PROFILE_FILE.unlink(missing_ok=True)
        # Clean up memories and affinity from DB
        wipe_player_memories(player_id)
        log.info("Deleted profile %s", player_id[:8])
        return True
    except OSError as e:
        log.warning("Failed to delete profile %s: %s", player_id[:8], e)
        return False


def needs_onboarding() -> bool:
    """Check if there are no profiles (first-time user)."""
    profiles = list_profiles()
    return len(profiles) == 0
