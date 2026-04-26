"""Per-million-token rates for the LLMs Kourai uses.

Source: Anthropic public pricing page as of April 2026 (cross-referenced
against finout.io and benchlm.ai 2026 pricing summaries). Output rate
is consistently 5x the input rate across every Claude tier; cache
reads land at 0.1x input (90% discount), 5-minute cache writes at
1.25x input.

When a new tier ships or rates change, update :data:`ANTHROPIC_PRICING`;
the cost helpers below derive everything else.
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
# Rates are uniform: cache_read = input * 0.1, cache_write_5min = input * 1.25.
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


def get_model_pricing(model: str) -> ModelPricing | None:
    """Look up rates for a model id; return ``None`` if unknown.

    Unknown models (Gemini, Ollama, anything we haven't priced)
    return ``None`` so callers can either skip the cost line or
    fall back to a token-count-only display. We don't guess —
    silently quoting the wrong number is worse than quoting none.
    """
    return ANTHROPIC_PRICING.get(model)


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
