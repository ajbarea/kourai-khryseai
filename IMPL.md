# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **`tier` kwarg symmetry on
`chat_with_tools` + `chat_stream`** (additive completion of PR #30)

---

## Plan-of-record

End state: every LLM-call entry point in `kourai_common.llm` accepts
the `tier` kwarg. Pure additive — no behavior change for existing
callers, the kwarg defaults to `None` which preserves the env-driven
`KOURAI_MODEL_TIER` behavior.

PR #30 added it to `chat()`. This finishes the job for `chat_stream()`
(used by Metis spec generation, Dokimasia test generation) and
`chat_with_tools()` (used by Techne / Kallos / Dokimasia for the
agentic file-op loop).

### Change ✅ 2026-04-26

- [x] `shared/src/kourai_common/llm.py::chat_stream`: added
      `tier: str | None = None` kwarg, forwards to `get_model`.
      Docstring updated.
- [x] `shared/src/kourai_common/llm.py::chat_with_tools`: added
      `tier: str | None = None` kwarg (kw-only since the function
      already uses `*`), forwards to `get_model`. Docstring updated.
- [x] No callers updated — pure additive. Future callers (e.g., a
      cheap-tier lint loop for Kallos auto-fixes) can pin without
      additional plumbing.

### Tests ✅ 2026-04-26

- [x] `tests/unit/test_llm.py::TestChatTierKwarg` extended from 2
      to 6 tests:
      - `test_chat_stream_tier_kwarg_passed_to_get_model`
      - `test_chat_stream_default_tier_preserves_callers`
      - `test_chat_with_tools_tier_kwarg_passed_to_get_model`
      - `test_chat_with_tools_default_tier_preserves_callers`
      - Plus the existing 2 tests for `chat()` from PR #30.
- [x] Each "default tier preserves callers" test is a backward-compat
      regression guard so a future refactor can't silently break the
      contract.

---

## Notes / open questions

- **Why no caller changes in this PR?** Nothing in the codebase
  needs the override on `chat_stream` or `chat_with_tools` today.
  Metis's M14 `discuss_tradeoffs` (the only current cheap-tier
  pinned caller) goes through `chat()`. Adding the kwarg now means
  future callers don't need a llm.py change to pin a tier.

- **Plausible future callers worth keeping in mind:**
  - Kallos's `apply_lint_fixes` — lint fixes are mechanical; cheap
    tier might suffice.
  - Dokimasia's `generate_tests_stream` for trivial test files.
  - Aidos's slop detection (currently uses `chat`) if it ever moves
    to streaming.

- **No `chat_stream(..., tier=...)` smoke today.** chat_stream is
  used by Metis's `create_spec_stream` which doesn't pin tier; the
  kwarg is dormant on real traffic. Mock-based unit tests cover it
  in isolation.

---

## Up next (queued, not yet active)

- **T8 follow-up** (ParallelContext shared buffer feeding Metis's
  partial output back into the classifier prompt to enrich the
  smart-tier read-back). Substantial async work.
- **T4 follow-up from M13** (`[forge_intent]` block on user message
  to specialists). Small.
- **M9** (Opus 4.6 → 4.7 in `MODELS_SMART["metis"]`) — one-line bump,
  unblocked by Round 6.
- **M2** (`kourai-forge-mcp` server) — real architectural milestone.
- **M15** (forge logging architecture) — operational hygiene.
- **M5** (UID alignment for forge worktrees) — quality-of-life.
- **M7** (a2a-sdk 1.0.x migration) — properly scoped.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor.
