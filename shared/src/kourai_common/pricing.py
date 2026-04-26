"""Per-million-token rates for the LLMs Kourai uses.

Sources: Anthropic public pricing page (cross-referenced against
finout.io and benchlm.ai 2026 summaries) and Google's Gemini pricing
page (https://ai.google.dev/gemini-api/docs/pricing) as of April 2026.

Anthropic rates are uniform: output = 5x input, cache_read = 0.1x input,
5-minute cache_write = 1.25x input. Gemini doesn't structure cache cost
the same way (storage is billed per-hour, not per-write), so
``cache_write_5min_per_m`` is left at 0 for Gemini entries — we'll
under-count Gemini cache writes by that amount, which is a known
limitation noted in the test plan.

When a new tier ships or rates change, update the relevant table below;
:func:`get_model_pricing` searches both ANTHROPIC_PRICING and
GEMINI_PRICING in turn.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kourai_common.usage import AgentUsage

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelPricing:
    """Per-million-token rates for one model id."""

    input_per_m: float
    output_per_m: float
    cache_read_per_m: float
    cache_write_5min_per_m: float


# April 2026 published rates (per million tokens, USD).
# Anthropic invariants: output = 5x input, cache_read = 0.1x input,
# cache_write_5min = 1.25x input.
ANTHROPIC_PRICING: dict[str, ModelPricing] = {
    "anthropic/claude-haiku-4-5-20251001": ModelPricing(
        input_per_m=1.0,
        output_per_m=5.0,
        cache_read_per_m=0.10,
        cache_write_5min_per_m=1.25,
    ),
    "anthropic/claude-sonnet-4-6": ModelPricing(
        input_per_m=3.0,
        output_per_m=15.0,
        cache_read_per_m=0.30,
        cache_write_5min_per_m=3.75,
    ),
    "anthropic/claude-opus-4-6": ModelPricing(
        input_per_m=5.0,
        output_per_m=25.0,
        cache_read_per_m=0.50,
        cache_write_5min_per_m=6.25,
    ),
    "anthropic/claude-opus-4-7": ModelPricing(
        input_per_m=5.0,
        output_per_m=25.0,
        cache_read_per_m=0.50,
        cache_write_5min_per_m=6.25,
    ),
}


# Gemini April 2026 rates. 2.5-pro uses the under-200K-context tier (most
# of our calls fit easily); long-context calls would land slightly higher
# but the gap is small and the under-counting is documented.
# cache_write_5min_per_m left at 0 — Gemini's caching pricing is per-hour
# storage, not per-write; the model doesn't fit our 4-rate shape cleanly.
GEMINI_PRICING: dict[str, ModelPricing] = {
    "gemini/gemini-2.0-flash": ModelPricing(
        input_per_m=0.10,
        output_per_m=0.40,
        cache_read_per_m=0.01,
        cache_write_5min_per_m=0.0,
    ),
    "gemini/gemini-2.5-pro": ModelPricing(
        input_per_m=1.25,
        output_per_m=10.0,
        cache_read_per_m=0.125,
        cache_write_5min_per_m=0.0,
    ),
    "gemini/gemini-2.5-flash": ModelPricing(
        # Listed for completeness — used by the M6 ElevenLabs migration
        # path's voice-lab tooling, not by core agents today.
        input_per_m=0.30,
        output_per_m=2.50,
        cache_read_per_m=0.03,
        cache_write_5min_per_m=0.0,
    ),
}


# Unified lookup table — order matters for keyspace clarity but not
# resolution since model ids carry their provider prefix.
_ALL_PRICING: dict[str, ModelPricing] = {**ANTHROPIC_PRICING, **GEMINI_PRICING}


def get_model_pricing(model: str) -> ModelPricing | None:
    """Look up rates for a model id; return ``None`` if unknown.

    Unknown models (Ollama, anything we haven't priced) return ``None``
    so callers can either skip the cost line or fall back to a
    token-count-only display. We don't guess — silently quoting the
    wrong number is worse than quoting none.
    """
    return _ALL_PRICING.get(model)


def compute_cost(model: str, usage: AgentUsage) -> float | None:
    """Compute USD cost for one agent's accumulated usage.

    Returns ``None`` for unknown models so the CLI can render
    ``$ — `` instead of an inflated zero.
    """
    rates = get_model_pricing(model)
    if rates is None:
        return None
    input_cost = (usage.input_tokens / 1_000_000) * rates.input_per_m
    output_cost = (usage.output_tokens / 1_000_000) * rates.output_per_m
    cache_read_cost = (usage.cache_read_tokens / 1_000_000) * rates.cache_read_per_m
    cache_write_cost = (usage.cache_write_tokens / 1_000_000) * rates.cache_write_5min_per_m
    return input_cost + output_cost + cache_read_cost + cache_write_cost
