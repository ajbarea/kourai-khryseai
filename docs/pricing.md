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
    | `smart` | Claude Sonnet 4.6 + Opus 4.7 (Metis) | All agents (Opus for Metis only) |

=== "Google :material-google:"

    | Tier | Model | Used by |
    |---|---|---|
    | `cheap` | Gemini 2.5 Flash-Lite | All agents |
    | `standard` | Gemini 2.5 Pro + Flash-Lite | Hephaestus / Metis / Techne on Pro, others on Flash-Lite |
    | `smart` | Gemini 2.5 Pro (Puck / Aidos on Flash-Lite) | All agents |

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
    1. **`smart` tier is expensive.** Opus 4.7 costs ~5× more than Haiku 4.5.
       Only use when you need maximum planning quality.
    2. **Gemini 2.5 Pro thinking tokens are unpredictable.** Reasoning tokens
       count as output at full rate. Monitor usage in Google AI Studio.
    3. **Pipeline is sequential** — core specialists make 6 billed API calls, no fan-out. Companion spirits and validators add 1–4 more calls when triggered.
    4. **Streaming has the same cost as non-streaming.** Only affects delivery, not billing.

## Prompt Caching

Every agent system prompt is marked `cache_control: ephemeral` so repeated
calls within a Techne / Kallos / Dokimasia tool-use loop pay the cached-read
rate (≈10% of input cost) instead of the full input rate. Iterations 2–N of
each fix loop hit the cache for the `[system + tools + initial-user]` prefix
— typically 2K–10K tokens of file contents and git context.

Cross-call caching of just the agent system prompt does **not** pay today
(the prompts are below Anthropic's 2048-token Sonnet 4.6 and 4096-token
Haiku 4.5 / Opus 4.7 minimum-cacheable thresholds, [verified June 2026](https://platform.claude.com/docs/en/build-with-claude/prompt-caching));
within-loop is the actual win.

## In-session usage tracking

`/usage` (alias `/cost`) in the CLI prints a per-(agent, model) breakdown of
calls, input / output / cache-read / cache-write tokens, and dollar cost for
the current REPL session. `/reset_usage` zeros the counter.
