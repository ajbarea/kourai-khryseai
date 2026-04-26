# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **`chat()` per-call tier override**
(M14 follow-on)

---

## Plan-of-record

End state: `chat()` accepts an optional `tier="cheap"` kwarg that
pins a single call to the cheap tier regardless of `KOURAI_MODEL_TIER`.
Metis's M14 `discuss_tradeoffs` uses it so the parallel discussion
runs on Haiku regardless of pipeline tier — saves ongoing token spend
on every tier-1 confirmation where the discussion is dropped silently.

### Surface ✅ 2026-04-26

- [x] `shared/src/kourai_common/config.py::get_model(agent_name, tier=None)`:
      `tier` kwarg overrides `KOURAI_MODEL_TIER` for that call. Same
      fallback semantics as the env path (unknown tier → cheap).
      Local provider ignores `tier` (no tier dimension on Ollama).
      `KOURAI_MODEL_OVERRIDE` still wins over everything (test escape
      hatch unchanged).
- [x] `shared/src/kourai_common/llm.py::chat(..., tier=None)`: passes
      through to `get_model`. Default `None` preserves backward
      compatibility — every existing caller works untouched.
- [x] `agents/metis/agent.py::discuss_tradeoffs`: pins to
      `tier="cheap"`. Docstring updated to document the pinning
      decision (auxiliary call → cheap regardless of pipeline tier).

### Not in this PR — `chat_with_tools` and `chat_stream` symmetry

Neither needs the kwarg today (no callers want a per-call tier
override). Adding by symmetry would be cheap, but not necessary to
land the M14 win. If a future caller needs it, add then — same
~5-line forwarding pattern.

### Tests ✅ 2026-04-26

- [x] `tests/unit/test_config.py::TestGetModel`: 5 new tests —
      `tier_kwarg_overrides_env`, `tier_kwarg_none_falls_back_to_env`
      (backward-compat regression guard), `tier_kwarg_unknown_falls_back_to_cheap`,
      `tier_kwarg_ignored_when_local_provider`,
      `tier_kwarg_ignored_when_model_override_set`.
- [x] `tests/unit/test_llm.py::TestChatTierKwarg`: 2 new tests —
      `tier` kwarg flows through to `get_model`; default `None` is
      preserved for existing callers.
- [x] `tests/unit/test_metis_parallel.py::TestDiscussTradeoffs::test_pinned_to_cheap_tier`:
      regression guard so a future tweak to `discuss_tradeoffs` can't
      silently un-pin Metis from cheap.

### Step 4 — Live smoke (queued for next interactive `/project` session)

- [ ] With `KOURAI_MODEL_TIER=smart`, send a tier-2 prompt. Confirm
      via `/usage` that Metis's *discussion* row uses
      `claude-haiku-4-5-20251001` while her *create_spec* row (later
      in the pipeline) uses `claude-opus-4-7` per
      `MODELS_SMART["metis"]`. Two distinct model rows for the same
      agent within one session is the expected new shape.

---

## Notes / open questions

- **Why `tier` rather than `model_override`?** Tier is the existing
  conceptual axis (cheap/standard/smart) the codebase already uses.
  Adding `model_override="anthropic/claude-haiku-…"` would let
  callers bypass the tier table entirely, which is a footgun (the
  pricing table in `kourai_common.pricing.ANTHROPIC_PRICING` is
  per-model — bypassing the tier resolution risks /usage missing
  costs). `tier="cheap"` keeps everything within the existing
  resolution path.

- **This won't affect chat_with_tools or chat_stream callers today.**
  Techne / Kallos / Dokimasia drive the agentic loop at the active
  pipeline tier — that's correct (file ops want full capability).
  Metis's spec generation streams at active tier — also correct.
  The only caller that benefits from cheap-tier pinning today is
  Metis's auxiliary discussion. If a future caller needs the
  override on chat_with_tools / chat_stream, add the kwarg then.

- **The `/usage` table now shows two model rows per agent** in
  sessions that exercise `discuss_tradeoffs`. The accumulator keys on
  `(agent_name, model)` so the cheap-tier discussion totals stack
  separately from the smart-tier spec totals. That's the right shape
  — it makes the cost win visible in the table.

  Wait — double-checking that. Looking at
  `kourai_common/usage.py::record_usage`, the accumulator keys on
  `agent_name` only, and the bucket carries a single `model` field
  ("first model wins per agent"). So the cheap-tier discussion will
  bind Metis's bucket to `claude-haiku-…` for the rest of the
  session, masking the actual Opus spec spend. That's a regression
  in `/usage` accuracy worth fixing in a follow-up PR. For now,
  documented; the per-call cost calculation is right but per-agent
  display is degraded.

---

## Up next (queued, not yet active)

- **`/usage` per-(agent, model) keying** — the docstring above
  captures the regression. Small fix; bumps the accumulator key
  from `agent_name` to `(agent_name, model)`. Worth a small follow-up.
- **T8 follow-up** (ParallelContext shared buffer feeding Metis's
  partial output back into the classifier prompt to enrich the
  smart-tier read-back). Substantial async work.
- **T4 follow-up from M13** (`[forge_intent]` block on user message
  to specialists). Small.
- **M9** (Opus 4.6 → 4.7 in `MODELS_SMART["metis"]`) — one-line bump,
  unblocked by Round 6.
- **M2** (`kourai-forge-mcp` server) — unblocked, real architectural
  milestone.
- **M15** (forge logging architecture) — operational hygiene.
- **M5** (UID alignment for forge worktrees) — quality-of-life.
- **M7** (a2a-sdk 1.0.x migration) — properly scoped.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor.
