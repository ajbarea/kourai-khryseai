# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **Test hygiene + a2a-sdk pin tightening**
(unscheduled — bundled per "stick the follow fixes into whatever IMPL.md
work you do next")

---

## Plan-of-record

End state: the push/PR fast lane stops eating CI minutes (and developer
attention) on transient Kokoro neural-inference timeouts, AND `uv lock`
stops auto-adopting the breaking a2a-sdk 1.0.x release until M7 is
properly migrated. Two unrelated hygiene items bundled because both
surfaced the same day from the same prior PR.

### Step 1 — Mark slow Kokoro tests ✅ 2026-04-26

- [x] `tests/unit/test_tts_backends.py`: `@pytest.mark.slow` on the 5
      tests that actually load the Kokoro neural model and synthesise
      audio (`test_kokoro_synthesize_returns_wav_bytes`,
      `_with_speed_override`, `_with_pitch_override`,
      `_invalid_voice_id_raises_error`, `_synthesize_to_file`). The
      config-validation tests (`_invalid_speed_rejected_at_config`
      etc.) stay on the fast lane — they're pure dataclass checks
      and never load the model.
- [x] `pyproject.toml`: registered the `slow` marker in
      `[tool.pytest.ini_options].markers`.

### Step 2 — Default the fast lane to `-m "not slow"` ✅ 2026-04-26

- [x] `scripts/test.py`: the `make test-unit` / `kourai-dev test-unit`
      invocation now passes `-m "not slow"`. Inline comment explains
      the rationale and points at the nightly path.
- [x] `.github/workflows/tests.yml`: the `Unit Tests` job pytest
      command grew the same `-m "not slow"` flag. Same inline
      explanation.

### Step 3 — Pin a2a-sdk back to `<1.0` ✅ 2026-04-26

- [x] `shared/pyproject.toml`: pin tightened from `<2.0` → `<1.0`
      with an inline block comment explaining the protobuf-migration
      finding and pointing at ROADMAP M7.
- [x] `hosts/cli/pyproject.toml` and `hosts/gui/pyproject.toml`:
      same tightening, one-line comments referencing
      `shared/pyproject.toml` for the full reasoning.
- [x] `uv lock --upgrade-package a2a-sdk` re-resolved the lockfile
      back to 0.3.26 and `uv sync --all-packages` confirms the
      installed version.

### Step 4 — Update ROADMAP M7 ✅ 2026-04-26

- [x] M7 entry rewritten with the 2026-04-26 finding: protobuf-based
      `Part` replaces the Pydantic shape the original entry
      anticipated; every construction site (not just inspection) needs
      rewriting; live A2A smoke against `make up` is required because
      the protobuf wire format has subtle oneof / default-value
      semantics that mocked tests won't catch.
- [x] Status flag updated: "planned · Bigger-than-the-firewall-claimed
      · Pyproject pinned to `<1.0` until M7 lands properly".

### Step 5 — Live smoke (queued for next interactive session)

- [ ] Run `make test-unit` locally → confirm "deselected: 5" or
      similar in the pytest summary, no `slow`-tagged Kokoro tests
      executed.
- [ ] Open the next PR → confirm Unit Tests job in CI completes
      faster than M11/usage PRs (Kokoro inference was eating ~30s of
      runner time before the fix).
- [ ] When the nightly workflow lands (currently AJ's WIP), point
      its pytest command at `tests/unit -m slow` to actually exercise
      the full Kokoro path on a daily cadence.

---

## Notes / open questions

- **Why pin `<1.0` instead of doing M7 now?** The migration is much
  bigger than the ROADMAP entry suggested. The dual-shape firewall in
  `a2a_utils.py` covered inspection (`hasattr`-based forward compat)
  but not construction. Every `Part(root=TextPart(text=...))` and
  `Part(root=FilePart(file=FileWithBytes(...)))` site in
  `remote_connections.py`, `hosts/cli/streaming.py`,
  `hosts/gui/client.py`, plus mocks in test files, needs rewriting
  for the protobuf-style API. Doing that without live A2A smoke is
  a recipe for shipping broken wire serialisation that mocked unit
  tests can't catch. Pin tighter, ship the rest, do M7 properly later.

- **Why not just delete the slow Kokoro tests?** Because they cover a
  real production code path — Kokoro is the primary VN/GUI TTS
  backend per the M6 ElevenLabs roadmap entry. We need the assertions
  to keep running, just not on every push. Nightly cron is the right
  cadence per the "Nightly = slow-test escape valve" convention.

- **The nightly.yml file in the working tree.** Untracked WIP from
  AJ. I deliberately didn't touch it — when AJ commits it, point the
  unit-test invocation at `tests/unit -m slow --no-cov` (or similar)
  so the slow path actually runs daily.

- **A note for whoever picks up M7.** Start by reading the A2A 1.0
  Python SDK README — the protobuf-style construction pattern is
  documented but reads very differently from the Pydantic 0.3.x
  examples. Run `uv run python -c "from a2a.types import Part;
  help(Part)"` to see the live shape; the inspector reveals the
  member fields clearly (`text`, `data`, `raw`, `url`, `filename`,
  `media_type`, `metadata`).

---

## Up next (queued, not yet active)

- **M2** (`kourai-forge-mcp` server) — gated on M1 Round 6 smoke.
- **M9** (Opus 4.6 → 4.7 in `MODELS_SMART["metis"]`) — one-line bump,
  also wants Round 6 smoke first. Pricing already in
  `ANTHROPIC_PRICING` so the bump is `/usage`-ready.
- **M5** (UID alignment for forge worktrees) — quality-of-life,
  needs live docker testing to verify.
- **M7** (a2a-sdk 1.0.x migration) — now that the pin is tightened
  and the scope is clearer, this is a focused future-PR target.
  Needs live A2A smoke against `make up`.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor
  on the board; high-DPI / accessibility win once it lands.
