# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-30 · Working on: **M18 Phase 1 — partial.**
Per-specialist migration to the URI-namespaced extension key
``"https://kourai.khryseai/ext/streaming/v1"`` with
``{"content_kind": "dialogue" | "status" | "code" | "spec"}`` nested
under it. Three of eleven specialists shipped to ``main`` 2026-04-30
— hephaestus pilot (#99), metis (#100), techne (#101). Eight
remaining: dokimasia, kallos, mneme (core pipeline) + puck, cupid,
aletheia, aidos, vn-bridge (companions + Ren'Py adapter). The host's
``or kind is None`` legacy fallback in ``hosts/cli/streaming.py``
retires when every specialist opts in. Phase 2 (SSML in dialogue
bodies) and Phase 3 (``KIND_CODE`` / ``KIND_SPEC`` distinct render
paths) are gated on full Phase 1. Pre-release perfection stance: no
workarounds.

## M18 Phase 1 — what's on `main`

- ``8658013 feat(M18): content-kind metadata contract + hephaestus pilot (#99)``
  ships ``shared/src/kourai_common/messaging.py`` with
  ``KOURAI_STREAMING_EXT_URI``, ``CONTENT_KIND_FIELD``,
  ``KIND_DIALOGUE`` / ``KIND_STATUS`` / ``KIND_CODE`` / ``KIND_SPEC``,
  ``set_content_kind`` / ``get_content_kind`` / ``kind_message``, and
  an optional ``kind=`` kwarg on every ``TaskUpdater`` helper.
  Hephaestus pilot tags CONFIRM_ORDER / INPUT_REQUIRED forward /
  parallel-discussion as ``KIND_DIALOGUE``; routing + pipeline status
  as ``KIND_STATUS``. Specialist relays stay untagged so the legacy
  emoji-prefix path keeps routing during the migration window. Host
  ``hosts/cli/streaming.py`` reads kind via ``get_content_kind`` and
  gates TTS on ``kind is None or kind == KIND_DIALOGUE``.

- ``31f846c feat(M18): tag metis emissions with content-kind metadata (#100)``
  tags all seven metis emissions: "Analyzing project structure...",
  streamed git status (🔍), "Drafting implementation spec...", M17
  recall narration ("Metis remembers..." → ``KIND_DIALOGUE``), streamed
  "Planning: <latest>" snippets every 5 chunks, "Spec complete", M17
  PAUSE input_required (``KIND_DIALOGUE``).

- ``5e6d603 feat(M18): tag techne emissions with content-kind metadata (#101)``
  tags all five techne emissions as ``KIND_STATUS``: "Reading existing
  code...", streamed git status (🔍), "Generating code changes...",
  streamed tool-call results (🔧 "<tool> <path> (ok|fail)"), "Applied
  N code changes to disk".

Audit cleanup that landed on the same branches:
- ``5ffa4cb chore(ci): silence ty warnings + transitive pydub noise`` —
  two `ty` ignore comments + filterwarnings entries for pydub
  ``SyntaxWarning`` (5x per test job, upstream-unmaintained, transitive
  via realtimetts) and ``RuntimeWarning`` (ffmpeg lookup). 2847 unit
  tests now run with 9 warnings, down from 20.
- ``927d464 chore(ci): bump actions/cache v4 → v5.0.5 for sister-repo parity``
  — flagged by ``/aj-sisters`` audit; v5 runs Node 24 + cache-service v2
  backend, runner ≥ 2.327.1.

## M18 Phase 1 — what's left (8 specialist migrations)

| Specialist | Role | Expected emissions |
|---|---|---|
| dokimasia | tester (pytest) | ``KIND_STATUS`` — "Running tests...", per-test progress, summary |
| kallos    | stylist (ruff) | ``KIND_STATUS`` — "Linting...", per-file fix events, summary |
| mneme     | commits (git) | ``KIND_STATUS`` for diff/group beats; ``KIND_DIALOGUE`` for "I have nothing to commit" + final commit narration |
| puck      | tutorial companion | ``KIND_DIALOGUE`` for player-directed nudges |
| cupid     | romance companion | ``KIND_DIALOGUE`` for player-facing dialogue |
| aletheia  | truth / fact read-side (M17) | TBD — read first |
| aidos     | shame / fact write-side (M17) | TBD — read first |
| vn-bridge | Ren'Py adapter | Different shape — emissions live in ``vn_bridge.py``, not ``agent_executor.py`` |

dokimasia + kallos are the most cadence-relevant after metis + techne
(they emit chatty per-step output that currently TTS-narrates each
chunk). mneme follows. The four companions + vn-bridge can land later;
they're less in the cadence path.

## Live-smoke evidence — 2026-04-30 morning

Driven via pexpect (``/tmp/m18_smoke_driver.py``) against containers
rebuilt at the URI shape (4614c92 + the hephaestus pilot kit). Settings:
``voice_enabled=false`` (WSL2 PortAudio default-output crackle blocked
audio-on smoke), ``yolo_enabled=false``. ``make rebuild`` took 848s.

| beat | timestamp (UTC) | observed |
|---|---|---|
| Driver sends prompt | 15:16:42 | "Plan a small fizzbuzz module with full pytest tests." |
| Hephaestus first execute | 15:16:44 | ``Hephaestus execute triggered`` |
| CONFIRM_ORDER read-back | 15:16:50 | ``CONFIRM_ORDER: smart "FizzBuzz module ... or the works?"`` |
| Driver sends ``yes`` | 15:16:53 | resume turn dispatched |
| Pipeline determined | 15:16:55 | ``metis -> techne -> dokimasia -> kallos`` (LLM routed 4-stage, no mneme this run) |
| All 4 specialists connected | 15:16:55 | ``hephaestus.remote_connections.Connected to {metis,techne,dokimasia,kallos}`` |
| Hephaestus → metis | 15:16:55 | ``Sending to metis: 117 chars`` |
| **M13 verification** | **15:16:58** | ``agents.metis.agent: Streaming spec for: [User]: Plan a small fizzbuzz module with full pytest tests.`` (M13 original-request relay intact on the URI shape) |
| Metis spec streams + dialogue gate | 15:17:05–15:17:16 | full FizzBuzz spec; ``AgentInputRequired`` bubbles through hephaestus |
| Driver sends ``100%`` | 15:17:16 | resume metis dialogue |
| Resumed turn complete | 15:17:18 | ``✨ Forged in 1.6s`` |

**M18 wire shape verified.** Targeted grep across all 11 specialist
container logs for ``KOURAI_STREAMING_EXT_URI`` / ``content_kind`` /
``set_content_kind`` / ``get_content_kind`` / ``kourai.streaming`` /
``kourai/ext/streaming`` returned zero hits in error contexts —
protobuf ``Struct`` round-trip on
``msg.metadata[URI] = {"content_kind": ...}`` works under live
container load. Three hephaestus tracebacks observed
(``AgentInputRequired``, ``GeneratorExit``, OpenTelemetry
``ValueError: Token created in a different Context``) are intentional
control flow + a known opentelemetry+asyncio context-detach issue;
none mention M18 constants.

**Audible cadence-diff** still isn't observable here because
``voice_enabled=false`` collapses both kinds to a no-TTS path. Unit
tests already cover the gating predicate in isolation
(``test_get_content_kind_reads_through_task_status_update_event``).
An audio-on smoke remains blocked on the WSL2 PortAudio crackling
tracked separately (``feedback_drive_smoke_yourself.md``,
``shared/src/kourai_common/audio.py`` comment).

## "100%" round-trip — investigated 2026-04-30, **by design (M17 is future-run, not in-flight resume)**

Initial flag: in the live smoke, after the driver answered metis's M17
dialogue gate ("Should I plan for pytest, unittest, or hypothesis?")
with "100%", the downstream pipeline (techne / dokimasia / kallos)
didn't execute and ``✨ Forged in 1.6s`` was just the resumed-turn
elapsed time. Initially triaged as either smoke-driver wording or a
hephaestus resume-routing gap.

Investigation: ROADMAP §M17 lines 510-518 are explicit — M17 is
**future-run preference recall**, not in-flight pipeline resume. The
designed flow:
1. Metis hits ``PAUSE: <kind> "<question>"`` token in spec generation
2. ``pause_state.stash_preference_kind`` saves
   ``(preference_kind, source_agent)`` keyed by ``context_id``
3. Metis's executor sends INPUT_REQUIRED, the metis task TERMINATES
4. Hephaestus catches ``AgentInputRequired`` and yields INPUT_REQUIRED
   to CLI; the pipeline run ENDS at that state
5. Player answers; CLI's ``_try_synthesise_pause_fact`` pops the stash
   and writes a project-scoped fact via ``synthesise_fact_from_pause``
6. The **next** development request in this project sees the fact via
   ``build_fact_context`` injected into metis's PLAYER CONTEXT block —
   metis no longer needs to ask

So the smoke's ``Forged in 1.6s`` is the EXPECTED outcome on a fresh
project. The pipeline doesn't continue mid-flight; the answer benefits
the next run. The original M13 ``CONFIRM_ORDER → "yes" → continue``
flow is a different mechanism (M13 is in-flight, M17 is post-pause).

**Implication for full-pipeline smokes:** to drive metis →
techne → dokimasia → kallos → mneme end-to-end in one run, the project
facts must be pre-seeded so metis doesn't pause at all. Two paths:
- **Pre-seed via ``/preferences set``** (M17 Phase 2 CRUD CLI) before
  the smoke prompt. Sets ``test_framework=pytest`` /
  ``coverage_target=100%`` etc. as project-scoped facts; metis reads
  them via ``build_fact_context`` and skips the PAUSE.
- **Two-run smoke**: first run pauses, stashes the fact; second run
  benefits from recall narration ("Metis remembers...") and runs
  through.

Either path is the right shape for a full-pipeline smoke once
dokimasia / kallos / mneme migrations land. Not a bug. The smoke
driver at ``/tmp/m18_smoke_driver.py`` should be updated to pre-seed
``test_framework=pytest`` rather than reply to the gate at runtime.

## Open issues — surfaced from the 2026-04-29 smoke (M18-adjacent or independent)

**Solved by completing M18:** comms-window streaming as discrete narrow
boxes (truncation appearance), final-render wide-box only-some-agents,
TTS gating universal, FACT-tag leakage into status, Mneme reading
905-char dialogue including markdown markup aloud.

**Independent UX bugs — small focused PRs:**
- `Pipeline complete` + `commit_count: 0` together with no soft-fail
  surface (#17)
- Per-agent CLI color coding via colored-background "badge" pattern
  (Okabe-Ito CVD-safe, NO_COLOR-aware) (#10)
- Music playlist sparse — 2 tracks (#11)
- Agent-card poll storm — 30+ GET ``/.well-known/agent-card.json`` per
  minute on idle agents (#12)
- Context7 MCP integration broken: ``MCP error -32602: Tool
  get-library-docs not found`` AND URL template emits literal
  ``[User]:`` placeholder (#14)
- Duplicate empty `Project root:` field at end of metis enriched
  prompt (#15)
- Phonemizer warning spam ("words count mismatch on 100.0% of the
  lines (1/1)") on every TTS call — downgrade to DEBUG (#22)
- Pre-warm Kokoro per-language at engine init (avoid first-speak pause
  when an agent in lang_code=b speaks for the first time) (#23)
- Explicit captions / TTS subtitle toggle for accessibility — SPEECH
  VS ACTION rule already provides de-facto captions; toggle would
  surface SPEECH VS ACTION violations (#19)

## Notes / open questions

- **MCP elicitation deferred-by-design.** Real-caller-driven only.
  Architectural notes from closed
  [PR #74](https://github.com/ajbarea/kourai-khryseai/pull/74) capture
  the round-trip design when the first forge MCP tool wants
  ``ctx.elicit()``.
- **MCP spec version pinned to 2025-11-25.** Spec drift watcher cron
  (``scripts/watch_protocols.py``, runs Sundays 13:00 UTC) flags any
  subsequent revision.
- **``run_post_task_hooks`` orchestration unwired.** Layer is fully
  tested but no production call sites; ``synthesise_fact_from_pause``
  lives directly in ``streaming.py`` as the pragmatic answer.
  Promotion is sibling work flagged for M5/M6.
- **Specialist parity for fact recall.** Today only metis reads
  ``build_fact_context`` with project scope; techne / kallos /
  dokimasia / hephaestus inherit the gap. Defer until a non-metis
  PAUSE caller surfaces.

## Up next — priority order

UX/DX is the default between milestones. Pre-release perfection
stance: no workarounds, web-search 2026 best practice before any
implementation, architectural fix over expedient patch.

1. **Finish M18 Phase 1 specialist migrations.** Suggested order:
   dokimasia → kallos → mneme (core pipeline, most cadence-relevant)
   then puck → cupid → aletheia → aidos → vn-bridge.
2. **Update smoke driver** to pre-seed project facts via
   ``/preferences set`` so metis skips the M17 PAUSE; full-pipeline
   smoke then runs end-to-end in one shot.
3. **Full-pipeline live smoke** once dokimasia / kallos / mneme land
   AND the smoke driver is updated — first run where the audible
   cadence-diff is observable end-to-end (still blocked on the
   audio-on path under WSL2; voice-off at minimum gives
   timing-cadence visibility).
4. **M18 Phase 2 — SSML in dialogue bodies.** Kokoro doesn't natively
   consume SSML; transitional strip-then-synthesize. ElevenLabs
   migration on M6 unblocks full SSML downstream.
5. **M18 Phase 3 — KIND_CODE / KIND_SPEC distinct render paths.** Drop
   the ``or kind is None`` legacy fallback once every specialist opts
   in.
6. **M20 — Audio-text synchronization.** Builds on M18 (kind routing)
   + M19 (RealtimeTTS word-timing API already wired via the ``on_word=``
   callback). 9-14s text-precedes-audio gap is a player-notices UX
   issue. See ROADMAP §M20.
7. **Independent UX bugs** from the smoke (above).
8. **Live VN smoke** — exercises the new vn_bridge ``/tts`` →
   ``RealtimeTTSEngine.synthesize_to_wav`` path.
9. **``docs/architecture/puck-first-run-tutorial.md``** — pairs with
   the M6 player-onboarding theme.
10. **M5 / M12 / M15 / M6 follow-ons** — see ROADMAP for scope.
