# API Pricing

Which providers Kourai Khryseai can use, which models map to each tier,
and what to watch out for cost-wise.

> For exact per-token rates, see the provider pricing pages linked below.
> Rates change frequently — this doc focuses on the **structure** that stays stable.

## Providers

| `KOURAI_PROVIDER` | You pay | Pricing page |
|---|---|---|
| `anthropic` (default) | Anthropic API | [claude.com/pricing#api](https://claude.com/pricing#api) |
| `google` | Google AI (Gemini API) | [ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing) |
| `local` | **Free** — runs on your GPU via Ollama | [ollama.com](https://ollama.com) |

## Model Tiers

=== "Anthropic :material-cloud:"

    | Tier | Model | Used by |
    |---|---|---|
    | `cheap` (default) | Claude Haiku 4.5 | All agents |
    | `standard` | Claude Sonnet 4.6 | Hephaestus, Metis, Techne |
    | `smart` | Claude Sonnet 4.6 + Opus 4.6 (Metis) | All agents (Opus for Metis only) |

=== "Google :material-google:"

    | Tier | Model | Used by |
    |---|---|---|
    | `cheap` | Gemini 2.0 Flash | All agents |
    | `standard` / `smart` | Gemini 2.5 Pro | Heavy agents / all agents |

    !!! warning "Google free tier"
        Free tier prompts are used to improve Google's products. Switch to Paid tier in AI Studio to opt out.

=== "Ollama :material-server: (free)"

    | Model | Used by | VRAM |
    |---|---|---|
    | `llama3.3:70b` | Hephaestus, Metis, Techne, Aletheia | ~40 GB |
    | `qwen2.5-coder:32b` | Dokimasia | ~20 GB |
    | `llama3.3:8b` | Kallos, Mneme, Puck, Cupid, Aidos | ~5 GB |

    No per-token charges. You pay electricity and hardware only.

## Rough Cost Per Pipeline

A typical development pipeline runs `hephaestus → metis → techne → dokimasia → kallos → mneme` (6 core LLM calls, ~12K input, ~8K output tokens). Companion spirits (Puck, Cupid) and quality validators (Aidos, Aletheia) fire on-demand — not every request triggers all 10 agents.

| Tier | Anthropic | Google (paid) |
|---|---|---|
| `cheap` | ~$0.05 | ~$0.005 |
| `standard` | ~$0.25–$0.40 | ~$0.10–$0.20 |
| `smart` | ~$0.40–$0.70 | ~$0.10–$0.20 |

Companion/validator calls add minimal cost — Puck and Aidos use Haiku across all tiers.

## What You Are NOT Charged For

Web search, code execution sandbox, image generation, audio input,
batch API discounts, and context caching storage — Kourai uses none of these.

## Cost Tips

!!! tip "Keep costs low"
    1. **`smart` tier is expensive.** Opus 4.6 costs ~5× more than Haiku 4.5.
       Only use when you need maximum planning quality.
    2. **Gemini 2.5 Pro thinking tokens are unpredictable.** Reasoning tokens
       count as output at full rate. Monitor usage in Google AI Studio.
    3. **Pipeline is sequential** — core specialists make 6 billed API calls, no fan-out. Companion spirits and validators add 1–4 more calls when triggered.
    4. **`max_tokens=4096`** caps output. Techne and Metis are the most
       expensive per call due to output length.
    5. **Streaming has the same cost as non-streaming.** Only affects delivery, not billing.

## Prompt Caching (not yet implemented)

!!! info "Future optimization"
    Every agent has a large static system prompt — an ideal caching candidate.
    Both Anthropic and Google offer 80–90% input cost savings on cached reads.
    LiteLLM supports this via the `cache_control` content block parameter.
