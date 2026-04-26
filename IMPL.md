# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **`/usage` follow-on — `/reset_usage`
+ Gemini pricing**

---

## Plan-of-record

End state: the `/usage` feature shipped earlier today gets two
follow-ons that close gaps surfaced when we wrote the original tests:

1. A `/reset_usage` slash command zeroes the session counter mid-REPL
   without restarting. Long sessions accumulate; sometimes the player
   wants a fresh baseline (e.g., comparing the cost of two approaches
   to the same task).
2. Gemini models render real dollar amounts instead of `$—` —
   `gemini/gemini-2.0-flash` and `gemini/gemini-2.5-pro` (the two
   currently in `MODELS_*_GOOGLE`) now have priced entries plus
   `gemini/gemini-2.5-flash` for the M6 ElevenLabs / voice-lab path.

### Step 1 — Gemini pricing entries ✅ 2026-04-26

- [x] `shared/src/kourai_common/pricing.py`: new `GEMINI_PRICING`
      dict with April 2026 published rates (Flash $0.10/$0.40,
      Pro $1.25/$10, 2.5 Flash $0.30/$2.50). The cache_read = 0.1x
      input invariant holds for Gemini too.
- [x] `cache_write_5min_per_m` left at 0.0 for Gemini entries —
      Gemini's caching pricing is per-hour storage, not per-write,
      and the 4-rate `ModelPricing` shape doesn't fit cleanly. We
      under-count Gemini cache writes by that amount; documented in
      the module docstring and asserted in
      `test_cache_write_left_at_zero_intentionally`.
- [x] Refactored `get_model_pricing()` to search a unified
      `_ALL_PRICING` table — Anthropic and Gemini coexist without
      callers caring which provider the model lives in.

### Step 2 — `/reset_usage` slash command ✅ 2026-04-26

- [x] `hosts/cli/completer.py`: registered
      `SlashCommand("reset_usage", "Zero the session token + dollar
      counter")` so it shows up in the live-filter slash menu and
      auto-surfaces in `/help`.
- [x] `hosts/cli/__main__.py`: handler right after `/usage` calls
      `kourai_common.usage.reset_session_usage()` and prints
      `Session usage cleared.` (dim, single-line confirmation).

### Step 3 — Tests ✅ 2026-04-26

- [x] `tests/unit/test_usage.py`: extended from 21 → 31 tests:
      - `TestGetModelPricing` updated — Gemini now returns rates
        instead of `None`; the unknown-model assertion swapped from
        Gemini to `openai/gpt-5` since Gemini got priced.
      - New `TestGeminiPricing` (4 tests) — spot-checks on Flash
        and Pro absolute rates, cache_read = 0.1x input invariant
        across providers, intentional cache_write zero.
      - `TestUsageSlashCommand`: original `test_unknown_model_…`
        switched to `ollama/llama3.3:70b` (the only remaining
        unpriced provider we use); new
        `test_gemini_model_now_renders_dollar_cost` asserts the
        new behavior end-to-end.
      - New `TestResetUsage` (2) + `TestResetUsageSlashCommand` (2)
        covering the new command's behavior and registration.
      - Whole file passes in 0.55 s.

### Step 4 — Live smoke (queued for next interactive `/project` session)

- [ ] Run a request that uses `KOURAI_PROVIDER=google`, then
      `/usage` → confirm Gemini agents now show real dollar amounts
      instead of `$—` and the footer hint disappears for them.
- [ ] After any session, `/reset_usage` then `/usage` → confirm the
      table is empty (`No usage recorded yet`).

---

## Notes / open questions

- **Gemini cache-write under-count.** Documented limitation. Gemini
  bills cache storage hourly, not per-write, so our 4-rate shape
  can't quote a per-write cost without making one up. Folks running
  Gemini long-context will see slightly under-quoted totals — the
  delta is small (cache writes are a small fraction of total usage
  on most calls) and the docstring + test name make the choice
  visible.

- **Why not consolidate `ANTHROPIC_PRICING` + `GEMINI_PRICING` into
  one table?** Two reasons. (1) The provider-specific invariants
  differ — Anthropic's tier-uniform 5x output ratio doesn't apply
  to Gemini, so per-provider invariant tests need separate tables
  to assert against. (2) Adding a new provider (xAI Grok, OpenAI)
  becomes a copy-paste of the Gemini block rather than touching a
  monolithic dict — clearer attribution, easier review.

- **`/reset_usage` only clears the usage counter.** It deliberately
  doesn't touch `context_id` (conversation memory), forge sessions,
  or any other session state. Clearing those would deserve its own
  command (e.g., `/reset_context`) — a separate concern.

---

## Up next (queued, not yet active)

- **M2** (`kourai-forge-mcp` server) — gated on M1 Round 6 smoke.
- **M9** (Opus 4.6 → 4.7 in `MODELS_SMART["metis"]`) — one-line bump,
  also wants Round 6 smoke first. Pricing already in
  `ANTHROPIC_PRICING`.
- **M5** (UID alignment for forge worktrees) — quality-of-life,
  needs live docker testing to verify.
- **M7** (a2a-sdk 1.0.x migration) — properly scoped now after the
  protobuf-migration finding; needs live A2A smoke against `make up`.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor
  on the board; high-DPI / accessibility win once it lands.
