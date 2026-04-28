# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-28 · Working on: **no active milestone** — today's
session was a UX/DX cleanup pass between milestones. Four PRs merged:
[#71](https://github.com/ajbarea/kourai-khryseai/pull/71)
(prompt fix to block Haiku's `read_file(".")` failure mode),
[#72](https://github.com/ajbarea/kourai-khryseai/pull/72)
(deslop 195 lines of unused `github_search_code` /
`introspect_database` scaffolds),
[#73](https://github.com/ajbarea/kourai-khryseai/pull/73)
(restore `Found 0 diagnostics` baseline via `Mapping` covariance for
read-only `tool_handlers`),
[#75](https://github.com/ajbarea/kourai-khryseai/pull/75)
(audio test isolation — resolve `AudioManager` via live module so
`importlib.reload` in `test_audio_env.py` stops poisoning the
`test_gui_audio_tts_engine.py` namespace).

M2 effectively closed: Changes 1/2/3 shipped previously
([roots](./ROADMAP.md#shipped) + the kourai-mcp-forge stdio server +
the three specialists routed through the bridge). Change 4 (MCP
elicitation client capability + INPUT_REQUIRED bridge) was attempted
this session as [PR #74](https://github.com/ajbarea/kourai-khryseai/pull/74)
and **closed unmerged** — the original "elicitation = spec-blessed
analog of CONFIRM_ORDER" framing turns out to be a category mismatch
(CONFIRM_ORDER lives at the A2A layer, not mid-MCP-tool-call), and
no forge MCP tool currently calls `ctx.elicit()`, so the 1165-line
bridge would have been anticipatory infrastructure with no caller.
Held until a real MCP-server-side elicitation use case appears
(natural candidate: `delete_file` confirming destructive deletes
against an uncommitted-changes guard).

---

## Up next (pick one when ready)

These come from prior ROADMAP audits + open paper trails. Not active
until AJ explicitly nominates one — UX/DX wins continue to be the
default between architectural milestones.

- **Smoke 1 re-run** — A2A pipeline through Hephaestus → Techne writes
  file. Architecture verified end-to-end on 2026-04-28 (PR #64 trace
  propagation working as designed); only blocker was Haiku tier's
  `read_file(".")` failure mode, which #71 fixes. Worth re-running
  next time the WSL2 docker bridge stops dropping outbound to
  `api.anthropic.com`. Recipe: `make up` + `tmux new-session ... make
  cli` from `plans/2026-04-28-live-smoke-handoff.md`.
- **Live VN smoke** — `make vn` exercises both fixes from PR #66
  (`K_RETURN` keysym + codex notification text-sub). `renpy lint` is
  clean; the live re-run is the only thing missing before that bug
  fully closes out.
- **TTS integration test flake** — `test_tts_kokoro_integration.py::
  TestBackendInteroperability::test_different_backends_same_voice_
  config` times out reaching `wss://speech.platform.bing.com` from CI.
  A `@pytest.mark.requires_external_tts` marker + a CI environment
  flag would skip it on network failure rather than burn a rerun.
- **`docs/architecture/puck-first-run-tutorial.md`** — sitting
  untracked in the working tree; if it's player-tutorial work AJ
  started, it pairs with the M6 player-onboarding theme.
- **Plan Mode toggle (Cline-style)** — persistent planning mode.
- **Background memory consolidation (Mneme "autoDream")** — pairs
  with the previously-shipped `/compact`.
- **Custom-agent-via-markdown registration (OpenCode-style)** —
  long-term direction; M2 has now landed so this is unblocked.
- **T8 follow-up** (ParallelContext shared buffer feeding Metis's
  partial output back into the classifier prompt).
- **M15** (forge logging architecture) — operational hygiene; pairs
  naturally with M16's trace-ID change since both touch
  `setup_logging`.
- **M5** (UID alignment for forge worktrees) — would let us drop
  the `safe.directory '*'` workaround from #42.
- **M7** (a2a-sdk 1.0.x migration) — the watcher's a2a-sdk-pypi
  entry will fire when 1.0.x stabilises. The `Message.metadata`
  migration item is queued under M7's scope as a follow-on once the
  SDK pin flips.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor.
- **M17** (HOTL answer persistence — project-scoped facts).
- **M16 follow-ons:**
  - Live trace-ID-in-Dozzle smoke (unit-tested but worth eyeballing
    in a real `make up` + smoked pipeline).
  - `.claude/skill-context.md` cross-link to `docs/observability.md`.
  - `scripts/watch_protocols.py` `kind="docker-tag"` digester for
    `amir20/dozzle` / `jaegertracing/jaeger` / `prom/prometheus`.

---

## Notes / open questions (carry-over from M2)

- **MCP elicitation deferred-by-design.** The MCP Python SDK gates
  capability declaration on callback presence — declaring `elicitation`
  with a stub callback violates the "host that lies" anti-pattern that
  Change 1 was specifically built to avoid. Real-caller-driven only.
  When the first forge MCP tool wants `ctx.elicit()`, the architectural
  notes from the closed [PR #74](https://github.com/ajbarea/kourai-khryseai/pull/74)
  diff capture the round-trip design (HTTP side-channel from CLI to
  specialist via new Starlette route, asyncio Future registry,
  contextvar emitter); that's the implementation reference, not a plan
  to ship now.
- **Smoke 1 deferred — environmental.** The 2026-04-28 attempt
  reached "architecture verified" but missed the live LLM-driven
  write because Haiku read `read_file(".")` as a permission lockout
  and abandoned. PR #71 fixes that at every layer the model sees
  (TOOL USE prompts in techne/kallos/dokimasia, MCP schema docstring,
  runtime error message). Re-run is queued for whenever
  `api.anthropic.com` outbound from agent containers stabilises.
- **MCP spec version pinned to 2025-11-25.** The spec drift watcher
  cron (`scripts/watch_protocols.py`) will flag any subsequent
  revision; today's wiring assumes that spec. Tool annotations being
  explicitly marked untrusted is a 2025-11-25 thing.
