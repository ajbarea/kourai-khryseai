# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **`/usage` per-(agent, model)
keying** (caveat-fix from yesterday's tier-override PR)

---

## Plan-of-record

End state: `/usage` shows one row per distinct (agent, model) pair
seen in the session — Metis on Haiku (M14 discussion) gets its own
row distinct from Metis on Opus (smart-tier spec), so the cheap-tier
override is *visible* as a cost win instead of silently masking the
spec spend.

### usage.py — bump key from str to (str, str) ✅ 2026-04-26

- [x] `shared/src/kourai_common/usage.py::SessionUsage.agents` —
      type changed from `dict[str, AgentUsage]` to
      `dict[tuple[str, str], AgentUsage]`. Module docstring updated
      to spell out the new keying and link it to M14.
- [x] `record_usage` — keys lookup on `(agent_name, model)`. Removed
      the "first model wins per agent" semantics; each new
      (agent, model) pair gets its own bucket.

### CLI display — show the tier column ✅ 2026-04-26

- [x] `hosts/cli/__main__.py::_show_usage_summary` — iterates
      `sorted(snapshot.agents)` (tuple keys, so multi-model rows
      group naturally by agent). Adds a `tier` column between
      `agent` and `calls`, populated from `_short_model_label`.
- [x] `_short_model_label` helper compresses model ids to fit the
      8-char column: `anthropic/claude-haiku-4-5-20251001` →
      `haiku-4-5`. Empty / unknown model returns `?` so the column
      never overflows.
- [x] Total row's separator widened to 80 chars to accommodate the
      new column. Padding adjusted.

### Tests ✅ 2026-04-26

- [x] `tests/unit/test_usage.py::TestRecordUsage`:
      - Existing single-model assertions updated to use tuple keys
        `("techne", "anthropic/claude-sonnet-4-6")`.
      - `test_first_model_wins_per_agent` REPLACED by
        `test_per_agent_per_model_keying` — the new behavior.
- [x] New `TestUsageSlashCommand::test_multi_model_agent_renders_two_rows`
      — drives `_show_usage_summary` with two Metis calls (Haiku +
      Opus), asserts both costs render distinctly + TOTAL sums.
- [x] New `TestShortModelLabel` (6 tests) — Haiku/Sonnet/Opus
      version segments preserved; Gemini provider strip; empty →
      `?`; unknown format truncated.
- [x] Whole `test_usage.py` passes in 0.56s — 38 tests (was 31 + 7
      new).

### Step 4 — Live smoke (queued for next interactive `/project` session)

- [ ] With `KOURAI_MODEL_TIER=smart`, send a tier-2 prompt. Then
      `/usage` — confirm Metis appears as TWO rows: one
      `metis | haiku-4-5` (the discussion), one `metis | opus-4-7`
      (the spec). Both costs separate.
- [ ] Single-model agents (Techne, Kallos, Dokimasia, Mneme,
      Hephaestus) still render as one row each.
- [ ] TOTAL row sums the dollar costs across all tier rows correctly.

---

## Notes / open questions

- **Why `dict[tuple[str, str], AgentUsage]` and not `list[AgentUsage]`?**
  Lookup-by-key on every `record_usage` call is O(1) with a dict,
  O(N) with a list (scan to find existing row). Sessions with 6+
  agents producing 30+ calls each makes the dict materially faster.
  Iteration is the same either way (`sorted(snapshot.agents)` works
  on dict keys).

- **Naming.** Kept `SessionUsage.agents` as the field name even
  though the values aren't strictly per-agent anymore. Renaming to
  `rows` would have broken every existing test assertion. Tradeoff:
  slightly misleading name for less churn. The docstring spells out
  the actual keying.

- **Tier column in /usage.** New 8-char column shows the model's
  short label. The TOTAL row keeps the old narrow alignment because
  totals aren't per-tier — they aggregate everything. The visual
  result: per-agent rows have a tier badge; the divider line
  separates them from the unbadged totals.

- **The `/reset_usage` flow is unchanged.** Resetting clears all
  buckets regardless of key shape.

---

## Up next (queued, not yet active)

- **T8 follow-up** (ParallelContext shared buffer feeding Metis's
  partial output back into the classifier prompt to enrich the
  smart-tier read-back). Substantial async work.
- **T4 follow-up from M13** (`[forge_intent]` block on user message
  to specialists). Small.
- **`chat_with_tools` and `chat_stream` tier-kwarg symmetry** — add
  by symmetry when a future caller needs it; ~5-line forwarding
  pattern from yesterday's PR.
- **M9** (Opus 4.6 → 4.7 in `MODELS_SMART["metis"]`) — one-line bump.
- **M2** (`kourai-forge-mcp` server) — real architectural milestone.
- **M15** (forge logging architecture) — operational hygiene.
- **M5** (UID alignment for forge worktrees) — quality-of-life.
- **M7** (a2a-sdk 1.0.x migration) — properly scoped.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor.
