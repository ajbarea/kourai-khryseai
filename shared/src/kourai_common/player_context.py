"""Prompt context builder — combines identity, memories, alignment, romance, personality, and virtue context into a single injectable prompt block."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from kourai_common.llm import cached_text_blocks
from kourai_common.player_constants import (
    AFFINITY_TIER_INSTRUCTIONS,
    AFFINITY_TIER_NAMES,
)

if TYPE_CHECKING:
    from kourai_common.player_profile import PlayerProfile

log = logging.getLogger(__name__)


# ── Prompt Context Builder ──────────────────────────────────────────────


_profile_cache: PlayerProfile | None = None
_profile_cache_ts: float = 0.0
_PROFILE_CACHE_TTL = 30.0  # Reload profile every 30 seconds max


def get_enriched_system_blocks(
    base_prompt: str,
    agent_name: str,
    *,
    static_suffix: str = "",
) -> list[dict[str, Any]]:
    """Return system content as cache-marked text blocks split static/dynamic.

    Block 0 (truly static): ``base_prompt`` plus optional ``static_suffix``.
    Cache-hits across the full session — only changes when the agent ships a
    new SYSTEM_PROMPT or the call site appends a different suffix.

    Block 1 (player-dynamic, optional): identity + memories + alignment +
    romance + personality adaptation + memory moments + virtues, joined.
    Resets when player state shifts. Omitted when no enrichment applies (no
    profile / no display_name).

    Both blocks carry ``cache_control={"type": "ephemeral"}`` so the
    prefix-cache machinery can read either breakpoint independently.

    The ``static_suffix`` kwarg is for call sites that pin extra truly-static
    text to a particular invocation — dokimasia's "Fix failing tests..."
    suffix, metis's "DISCUSSION MODE..." suffix. The suffix concatenates into
    Block 0 because it's static for that call site; bundling it into Block 0
    keeps Block 1 free of static text (so Block 1 cache-hits even for
    non-suffix invocations of the same agent that follow).

    Caches the player profile for 30s to avoid repeated disk reads.

    research(2026-05): post-#177 follow-on. Pre-fix shape concatenated
    truly-static SYSTEM_PROMPT with dynamic player context as a single
    string, so every player-state shift invalidated the cache for the
    static portion (1-3 K tokens of maiden personality + tool descriptions).
    Anthropic supports up to four cache_control breakpoints per request in
    increasing prefix order; using two for system content (static + player-
    dynamic) plus one for the summary plus one for the first user message
    fits the budget exactly. Source:
    https://platform.claude.com/docs/en/build-with-claude/prompt-caching.
    """
    global _profile_cache, _profile_cache_ts

    from kourai_common.player_profile import PlayerProfile

    static_text = base_prompt
    if static_suffix:
        static_text = f"{base_prompt}\n\n{static_suffix}"

    now = time.time()
    if _profile_cache is None or (now - _profile_cache_ts) > _PROFILE_CACHE_TTL:
        _profile_cache = PlayerProfile.load()
        _profile_cache_ts = now

    if not _profile_cache or not _profile_cache.display_name:
        return cached_text_blocks(static_text)

    ctx = build_player_context(_profile_cache, agent_name, top_k_memories=6)
    if not ctx:
        return cached_text_blocks(static_text)

    parts = [ctx]

    # Personality adaptation (tier + alignment shifts) — player-dynamic.
    try:
        from kourai_common.personality_adaptation import get_personality_adaptation

        adaptation = get_personality_adaptation(
            _profile_cache.player_id, agent_name, _profile_cache
        )
        if adaptation:
            parts.append(adaptation)
    except Exception:
        log.debug("Failed to get personality adaptation (non-critical)", exc_info=True)

    # Memory moments (probabilistic nostalgia callbacks) — player-dynamic.
    try:
        from kourai_common.memory_moments import generate_moment_context

        moment = generate_moment_context(_profile_cache.player_id, agent_name, _profile_cache)
        if moment:
            parts.append(moment)
    except Exception:
        log.debug("Failed to generate memory moment (non-critical)", exc_info=True)

    # Forge virtue context — psychological state for interjection awareness;
    # player-dynamic (mutates with virtue events).
    try:
        from kourai_common.virtues import get_virtue_context

        virtue_ctx = get_virtue_context(_profile_cache.player_id)
        if virtue_ctx:
            parts.append(virtue_ctx)
    except Exception:
        log.debug("Failed to get virtue context (non-critical)", exc_info=True)

    dynamic_text = "\n\n".join(parts)
    return cached_text_blocks(static_text, dynamic_text)


def build_player_context(
    profile: PlayerProfile,
    agent_name: str,
    top_k_memories: int = 8,
) -> str:
    """Build the player context block for injection into agent system prompts.

    Args:
        profile: The player's profile.
        agent_name: Current agent name.
        top_k_memories: Max memories to include.

    Returns:
        Formatted context string ready for prompt injection.
    """
    from kourai_common.player_affinity import get_affinity, get_affinity_tier
    from kourai_common.player_alignment import get_alignment_gated_instructions
    from kourai_common.player_memory import retrieve_relevant_memories
    from kourai_common.player_romance import get_romance_dialogue_instructions

    if not profile.display_name:
        return ""

    lines: list[str] = []

    # Identity section
    lines.append("=== PLAYER IDENTITY ===")
    name_str = profile.display_name
    if profile.tts_name and profile.tts_name != profile.display_name:
        name_str += f' (pronounced "{profile.tts_name}")'
    lines.append(f"Name: {name_str}")
    if profile.title:
        lines.append(f"Title: {profile.title}")
    if profile.role:
        role_desc = {
            "divine": "Divine — address with respectful admiration",
            "mortal": "Mortal — address as a fellow artisan",
            "hero": "Hero — address with comradely respect, as a proven champion",
            "devoted": "Devoted Master — address with formal adoration and devotion",
            "name_only": "No special role — address naturally, just by name",
            "custom": profile.preferences.get("custom_role_desc", ""),
        }.get(profile.role, profile.role)
        lines.append(f"Role: {role_desc}")
    if profile.pronouns:
        lines.append(f"Pronouns: {profile.pronouns}")

    # Alignment section
    lines.append("")
    lines.append("=== ALIGNMENT ===")
    lines.append(f"Sovereignty: {profile.sovereignty}/100 | Devotion: {profile.devotion}/100")
    lines.append(f"Archetype: {profile.archetype.title()}")

    # Relationship section
    aff = get_affinity(profile.player_id, agent_name)
    tier = get_affinity_tier(aff["affinity_score"])
    tier_name = AFFINITY_TIER_NAMES[tier]

    lines.append("")
    lines.append(f"=== RELATIONSHIP ({agent_name.title()} ↔ {profile.display_name}) ===")
    lines.append(f"Affinity: {tier_name} ({aff['interaction_count']} interactions)")
    if aff["romance_stage"] != "none" and not profile.romance_opted_out:
        lines.append(f"Romance: {aff['romance_stage'].title()}")
    lines.append(AFFINITY_TIER_INSTRUCTIONS[tier])

    # Memory section
    memories = retrieve_relevant_memories(profile.player_id, agent_name, top_k=top_k_memories)
    if memories:
        lines.append("")
        lines.append("=== PLAYER MEMORIES ===")
        for mem in memories:
            source_tag = ""
            src = mem.get("source", "")
            if src.startswith("gossip:"):
                origin = src.split(":", 1)[1]
                source_tag = f" (via {origin}'s gossip)"
            elif src == "player_stated":
                source_tag = " (player stated)"
            lines.append(f"- {mem['content']}{source_tag}")

    # Alignment-gated behaviour instructions
    gated = get_alignment_gated_instructions(profile, agent_name)
    if gated:
        lines.append("")
        lines.append(gated)

    # Romance dialogue instructions
    romance = get_romance_dialogue_instructions(profile.player_id, agent_name, profile)
    if romance:
        lines.append("")
        lines.append(romance)

    return "\n".join(lines)
