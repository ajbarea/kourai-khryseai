# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **M9 — Metis Opus 4.6 → 4.7 bump**

---

## Plan-of-record

End state: Metis runs on Anthropic's current flagship (Opus 4.7) at
the smart tier instead of Opus 4.6. Cheap-bump per the ROADMAP entry
— pricing equivalent (`ANTHROPIC_PRICING` already has both at $5/$25),
cache thresholds match (4096 tokens minimum on both Opus 4.6 and 4.7,
so the M4 caching markers carry over without re-tuning), behaviour
documented as super-set across Anthropic Claude minor versions.

Round 6 smoke (which AJ ran at session start) validated Metis's
planning loop end-to-end on Opus 4.6 — the JSON-schema specs land
clean. Bumping to 4.7 inherits that validation since the API contract
and prompt format are unchanged.

### Change ✅ 2026-04-26

- [x] `shared/src/kourai_common/config.py:40`: one-line change in
      `MODELS_SMART["metis"]` — `anthropic/claude-opus-4-6` →
      `anthropic/claude-opus-4-7`.
- [x] `tests/unit/test_config.py::test_tier_kwarg_overrides_env`:
      assertion bumped from `4-6` → `4-7` (the test exercises Metis's
      smart-tier resolution).
- [x] New `test_metis_smart_tier_is_opus_4_7` regression guard so a
      future accidental rollback names itself in the test failure.

### What's NOT in this PR

- No pricing change. Both Opus 4.6 and 4.7 are already in
  `ANTHROPIC_PRICING` at $5/$25 input/output (added during the
  /usage feature work). Bumping Metis just shifts which row her
  smart-tier traffic lands in; per-token cost is unchanged.
- No prompt change. Metis's `SYSTEM_PROMPT` in `agents/metis/agent.py`
  is API-version-agnostic — Anthropic minor bumps are documented as
  behaviour super-sets.
- No M4 caching re-tune. Both Opus models share the 4096-token
  minimum cache threshold per Anthropic's published pricing, so the
  `_mark_system_cacheable` / `_mark_first_user_cacheable` markers
  light up at the same boundaries.

### Step 4 — Live smoke (queued for next interactive `/project` session)

- [ ] With `KOURAI_MODEL_TIER=smart`, send any tier-2 prompt → confirm
      Metis spec generation runs on `claude-opus-4-7` (visible in
      `dev-latest.log` and in `/usage` after the call).
- [ ] Verify the spec format Metis emits is unchanged from Round 6's
      Opus 4.6 baseline — section headers, structure, FACT tags.

---

## Notes / open questions

- **Why now?** Round 6 unblocked it (Metis's planning loop validated
  on 4.6). The pricing was already in `ANTHROPIC_PRICING`. The cache
  thresholds match. There's no bigger-picture reason to keep 4.6
  pinned beyond inertia. Single-line-bump PRs are cheaper to revert
  than to delay.

- **Why not bump Sonnet too?** No newer Sonnet has shipped. When
  Sonnet 4.7 lands, similar one-line bump to `MODELS_SMART` and
  related tier maps; pricing already in the table by structure.

- **Why a regression test for a one-line change?** Future restructures
  of the model maps could silently roll Metis back. Naming the
  intended state ("Metis smart tier IS Opus 4.7") in a test gives
  whoever causes the regression a clear failure message instead of a
  surprise on the next live smoke.

---

## Up next (queued, not yet active)

- **T8 follow-up** (ParallelContext shared buffer feeding Metis's
  partial output back into the classifier prompt to enrich the
  smart-tier read-back). Substantial async work.
- **T4 follow-up from M13** (`[forge_intent]` block on user message
  to specialists). Small.
- **M2** (`kourai-forge-mcp` server) — real architectural milestone.
- **M15** (forge logging architecture) — operational hygiene.
- **M5** (UID alignment for forge worktrees) — quality-of-life,
  needs live docker testing.
- **M7** (a2a-sdk 1.0.x migration) — properly scoped, needs live
  A2A smoke.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor.
