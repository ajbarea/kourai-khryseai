# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **`/usage` CLI command** (M6 unprioritized list)

---

## Plan-of-record

End state: the player can type `/usage` mid-session and see a per-agent
breakdown of token spend (input/output/cache_read/cache_write) plus an
estimated dollar total using April 2026 published rates. Long pipelines
stop turning into billing surprises.

The infra was *almost* there: M4 already wired `_log_cache_usage` to
debug-log per-call usage from `response.usage`. This work upgraded
that debug log to a per-session accumulator with a CLI command.

### Step 1 — `kourai_common.usage` module ✅ 2026-04-26

- [x] New `shared/src/kourai_common/usage.py`: module-level
      `_SESSION` (`SessionUsage` dataclass) keyed by agent name.
      Per-agent `AgentUsage` carries (input/output/cache_read/
      cache_write/calls/model). Thread-safe via a single lock.
- [x] `record_usage(agent_name, response, model)` pulls counts using
      the same MagicMock-aware `_coerce_int` discipline as
      `_log_cache_usage` so unit tests that mock LLM responses can't
      inflate session totals with sentinel objects.
- [x] `get_session_usage()` returns the live snapshot;
      `reset_session_usage()` clears it for new-session boundaries.
- [x] All-zero responses don't create a bucket (avoids fake "0
      calls, 0 tokens" rows from agents that never actually ran).

### Step 2 — `kourai_common.pricing` module ✅ 2026-04-26

- [x] New `shared/src/kourai_common/pricing.py`: `ModelPricing`
      dataclass + `ANTHROPIC_PRICING` table for Haiku 4.5
      ($1/$5), Sonnet 4.6 ($3/$15), Opus 4.6/4.7 ($5/$25). Uniform
      cache rates: read = input × 0.1, 5-min write = input × 1.25.
      Source: Anthropic public pricing as of April 2026 (cross-referenced
      against finout.io and benchlm.ai 2026 summaries).
- [x] `get_model_pricing(model)` returns `None` for unknown models so
      the CLI renders `$ — ` instead of an inflated zero — silent
      mis-quotes are worse than no quote.
- [x] `compute_cost(model, usage)` does the per-million-token math
      across all four token classes, returns `None` for unknown
      models (same reasoning).

### Step 3 — Hook into llm.py ✅ 2026-04-26

- [x] `record_usage(agent_name, response, model=model)` called right
      after `_log_cache_usage` in `chat()` and `chat_with_tools()`.
      Two-line addition each.
- [x] `chat_stream()` not hooked — LiteLLM's streaming iterator
      doesn't surface a final `usage` block we can read inside the
      generator. Documented in the usage module docstring as a known
      undercount; the substantive Techne / Kallos / Dokimasia /
      Hephaestus traffic all goes through `chat()` or
      `chat_with_tools()` so the player still sees the load-bearing
      cost.

### Step 4 — `/usage` slash command ✅ 2026-04-26

- [x] `hosts/cli/completer.py`: added `SlashCommand("usage", "Show
      running token + dollar cost for this session")` so `/usage`
      shows up in the live-filter slash menu and in `/help`
      automatically (the help renderer reads `SLASH_COMMANDS`).
- [x] `hosts/cli/__main__.py`: `_show_usage_summary()` formats the
      session snapshot as a per-agent table (calls / input / output /
      cache_r / cache_w / cost). TOTAL row aggregates real numbers and
      the dollar-cost-only sum (unknown-model rows skipped from the
      cost total but still listed). When unknown models appear,
      footer hints at `kourai_common.pricing.ANTHROPIC_PRICING` so
      the next contributor knows where to add rates.
- [x] Wired the `prompt_text == "/usage"` branch right after
      `/model_tier` in the REPL loop.

### Step 5 — Tests ✅ 2026-04-26

- [x] `tests/unit/test_usage.py`: 21 tests across 5 classes:
      - `TestRecordUsage` (7) — first-call-creates-bucket, accumulate,
        per-agent isolation, first-model-wins, missing-usage no-op,
        all-zero no-op, MagicMock dropped.
      - `TestPricingTable` (4) — invariant checks (5x, 0.1x, 1.25x
        ratios) + spot-check on Sonnet/Opus/Haiku absolute rates.
      - `TestGetModelPricing` (2), `TestComputeCost` (5),
        `TestUsageSlashCommand` (3 — empty, full breakdown, unknown
        model).
      - Autouse fixture resets `_SESSION` before AND after each test
        so cross-test bleed is impossible.
      - Whole file passes in 0.91 s.

### Step 6 — Live smoke (queued for next interactive `/project` session)

- [ ] Issue any prompt that exercises Hephaestus → Techne → Dokimasia
      pipeline. After it completes, type `/usage`. Confirm:
  - Each agent shows non-zero `calls` and matching token totals.
  - Cost column shows non-zero dollar amounts for Anthropic agents.
  - TOTAL row matches the sum of the agent rows.
- [ ] Issue several prompts in a row. Confirm `/usage` shows
      cumulative totals (the accumulator survives across turns).
- [ ] If running `KOURAI_PROVIDER=google`: confirm Gemini agents
      render `$—` and the footer hint mentions `gemini/gemini-…`.

---

## Notes / open questions

- **Why a separate `usage.py` module instead of folding into `llm.py`?**
  Keeps the accumulator testable in isolation (no LiteLLM import path,
  no httpx side effects). The autouse-fixture pattern relies on being
  able to reset module-level state cheaply per test.

- **Streaming undercount.** `chat_stream()` is used by Metis's
  `create_spec_stream` and Dokimasia's `generate_tests_stream`. Both
  display text live; neither writes to disk. The user will see those
  agents' rows show fewer tokens than they actually consumed. Acceptable
  for a first cut; if/when LiteLLM exposes a way to read the final
  aggregate from inside the iterator, hook it.

- **Per-call vs per-tier model tracking.** `record_usage` keeps the
  *first* model id seen per agent. A mid-session `KOURAI_MODEL_TIER`
  swap would silently keep computing costs at the old tier's rate
  for that agent. Out of scope for now — the configuration is
  process-lifetime, not per-call.

- **Gemini / Ollama pricing.** Not in `ANTHROPIC_PRICING` today.
  Gemini rates are knowable; Ollama is free (local). Add them when
  AJ uses those providers in anger; until then `$—` plus the footer
  hint is the right behavior.

---

## Up next (queued, not yet active)

- **M2** (`kourai-forge-mcp` server) — gated on M1 Round 6 smoke.
- **M9** (Opus 4.6 → 4.7 in `MODELS_SMART["metis"]`) — one-line bump,
  also wants Round 6 smoke first. (Pricing already in
  `ANTHROPIC_PRICING` so the bump is also `/usage`-ready.)
- **M5** (UID alignment for forge worktrees) — quality-of-life,
  needs live docker testing to verify.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor
  on the board; high-DPI / accessibility win once it lands.
- **Strict tool use** (M6 list) — once we've felt the M1 toolset's
  shape under live traffic, turn `strict: true` on for forge tools
  to guarantee schema conformance. Cross-provider behavior through
  LiteLLM needs a quick web-research pass first.
