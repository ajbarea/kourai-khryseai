# Player Projects — Manual Smoke Todo

Goal: prove the `/project` REPL flow works end-to-end against a live Hephaestus.
The unit tests + scripted smoke covered everything except the interactive REPL
wiring in `hosts/cli/__main__.py`. This is what's left.

Pour coffee. Open this file. Tell me you're starting and I'll guide each step.

---

## Pre-flight (5 min)

- [ ] Pull latest, confirm working tree clean: `git status`
- [ ] Confirm tests still green: `make test-unit` (expect 27 sandbox/project/forge tests passing)
- [ ] Confirm sandbox image still there: `docker image ls kourai-sandbox`
  (rebuild with `make sandbox-image` if it's gone)
- [ ] Confirm `.env` has working `ANTHROPIC_API_KEY` or `GEMINI_API_KEY`

## Round 1 — Host runner, happy path (15 min) — DONE 2026-04-20

- [x] **Terminal A:** `make up` → wait for "all agents ready" / no red errors
- [x] **Terminal B:** `make cli` → REPL prompt appears
- [x] Type `/` → confirm live-filtering popup shows commands (↑/↓, Tab, Enter)
- [x] Type `/help` → confirm the `/project …` group shows up in help text
- [x] `/project new hello-forge --template python`
- [x] `/project list` → see hello-forge listed
- [x] `/project use hello-forge` → "active project" line printed
- [x] Send a real prompt (plain chat, NOT `/project new <task>`): greet() task
- [x] `/project status` → one active forge session
- [x] `git log --all --oneline` in project: forge/ branch present, main untouched
- [x] `/project accept` (no id → latest active) → ff-merge, commit `083df04 forge: b0ff6f76 pipeline output` on main
- [x] `/project status` → no active sessions

## Round 2 — Discard path (5 min) — DONE 2026-04-20

- [x] `/project use hello-forge`; chat task: farewell() in src/farewell.py
- [x] Pipeline completes (Metis/Techne/Dokimasia/Kallos all completed); session `41cbbcb2` marked pending
- [x] `/project discard` (no id → latest) → "Session 41cbbcb2 discarded"
- [x] Follow-up `/project status` → "No active forge sessions"
- [x] main HEAD still `083df04` (unchanged), no `farewell.py` on disk, no `forge/…-fa` branch
- [x] DB row: `(41cbbcb2…, discarded, 2026-04-20T22:01:53Z, forge/20260420-175327-add-a-function-called-fa)`

## Round 3 — Container sandbox (10 min)

- [ ] Stop `make cli` in Terminal B
- [ ] Restart with sandbox: `KOURAI_SANDBOX=container make cli`
- [ ] `/project use hello-forge`
- [ ] Send: `add a function add(a,b) that returns a+b and a passing test`
- [ ] In **Terminal D:** `watch -n1 docker ps`
  - Expected: ephemeral `kourai-sandbox` containers appear during agent's pytest/ruff runs, gone right after
- [ ] After stream: `/project accept <id>` → confirm commit landed on main same as Round 1

## Round 4 — Safety (5 min, optional but worth it)

- [ ] Still in container mode, send: `write and run a script that does requests.get('http://example.com') and prints the body`
  - Expected: agent's run fails with DNS / network error (proves `--network none` is enforced inside the player loop, not just in unit tests)
- [ ] Send: `write a script that does open('/etc/passwd','w').write('lol')`
  - Expected: `PermissionError` from inside the container; host `/etc/passwd` untouched (`sudo head -1 /etc/passwd` to confirm)
- [ ] `/project discard <id>` to clean up

## Round 5 — No-Docker fallback (3 min)

- [ ] Stop CLI. Run: `KOURAI_SANDBOX=container PATH=/usr/bin:/bin make cli` (strip docker from PATH)
  - Expected: warning line "KOURAI_SANDBOX=container but `docker` not found … falling back to HostRunner"
  - Then REPL works normally (host runner)

## Round 6 — M1 tool-use migration validation (5 min) — DONE 2026-04-26

This validates the regex parser → provider tool-use swap in `chat_with_tools`.
Re-runs Round 1's accept path and Round 2's discard path with the new wiring.

**Result: clean pass.** Both 6a accept and 6b discard executed end-to-end.
22 `'type': 'tool_use'` frames in `docker logs kourai-khryseai-techne-1`
(with `toolu_*` IDs proving real provider blocks); 11 `'type': 'tool_result'`
frames closing the loop; **zero `parse_and_apply_fixes` hits** across all 6
agent containers (techne, hephaestus, metis, dokimasia, kallos, mneme).
Wall-clock: 244.8s on 6a, 418.6s on 6b — both under the 462s v2 baseline.

**Note for future smoke recipes:** the original grep targets (`logs/dev-latest.log`)
were wrong — that file is the dev-runner wrapper output, not agent traces.
The agent log volume mounts to host are stale; live traces only live inside
containers today. M15 (forge logging architecture, ROADMAP) fixes this.
Until then, validate tool_use frames via `docker logs kourai-khryseai-techne-1`,
not `logs/dev-latest.log`.

### Pre-flight status (verified 2026-04-22)

Remote prep complete — all non-interactive checks green. What's left is
strictly the live REPL loop.

- ✓ `parse_and_apply_fixes` has zero hits in source (`rg -n --type py`)
- ✓ `tool_use` debug log wired at `shared/src/kourai_common/llm.py:440`
  (`log.debug("tool_use %s args=%s result=%s", name, args, result[:200])`)
- ✓ Unit suite: 2322 passed in 95s (matches IMPL.md Step 4 claim)
- ✓ `kourai-sandbox:latest` image built (874 MB, 189 MB content)
- ✓ `.env` has working `ANTHROPIC_API_KEY` and `GEMINI_API_KEY`
- ✓ Working tree clean, main in sync with `origin/main`

### Live loop (sit down at PC, paste commands) — completed 2026-04-26

- [x] **Terminal A:** `make up` — all 15 containers healthy, no red errors
- [x] **Terminal B:** `make cli` — REPL prompt, Hephaestus connected at 10000
- [x] `/project use hello-forge`
- [x] **Round 6a — accept**: sent `add a function double(n) that returns n*2
      and a passing test`. Pipeline ran end-to-end (metis → techne → dokimasia
      → kallos → mneme), 5/5 agents completed.
- [x] After streaming, validated tool_use via:
      `docker logs kourai-khryseai-techne-1 | grep -cE "['\"]type['\"]\s*:\s*['\"]tool_use['\"]"`
      → **22 hits** with `toolu_*` IDs proving real provider blocks.
      *(Note: the original grep target — `logs/dev-latest.log` — was wrong;
      that file is dev-runner wrapper output, not agent traces. M15 fixes
      this. Until then, use `docker logs` for tool_use validation.)*
- [x] `parse_and_apply_fixes` count across all 6 agent containers: **zero**
      (`for c in techne hephaestus metis dokimasia kallos mneme; do count=$(docker logs kourai-khryseai-${c}-1 2>&1 | grep -c parse_and_apply_fixes); echo "$c: $count"; done`)
- [x] `/project status` → one active forge session (`946e593a`)
- [x] `/project accept` → ff-merge succeeded, `ac4c7d8 forge: 946e593a pipeline
      output` on main, `double()` lives in `src/math.py` with type hints and
      a 4-test suite passing.
- [x] **Round 6b — discard**: sent `add a function triple(n) that returns n*3
      and a passing test`. Pipeline ran clean, session `a1efdf42` pending.
      `/project discard` → "Session a1efdf42 discarded".
  - `git log -1` on main: unchanged (still `ac4c7d8`)
  - `git log -1` on main is unchanged from 6a
  - no `triple.py` on disk
  - `forge/` branch for the discarded session is gone (only `* main` in
    `git branch -a`); no `triple.py` or `triple()` on disk in `src/math.py`
- [x] **Wall-clock check**: 6a was **244.8s** (well under the 462s v2 baseline,
      ~53% of baseline). 6b was **418.6s** (still under baseline, slower than
      6a — Techne did more reads, plus the dead-zone before pipeline
      announcement varied between runs).

### Follow-up issues filed during the run

All five player-facing bullets shipped in focused PRs since this run; only
the M15 logging architecture work is left, and that lives on the M15
roadmap entry rather than as a Round 6 follow-up. Git history has the
canonical record:

- ✅ Branch label sanitization (#34)
- ✅ `read_file` schema description rejects directory paths (#34)
- ✅ Git context discovery — agents now run `git status` with `cwd=` set
  to the worktree (#42 + per-agent executors)
- ✅ CLI greeting names the speaking maiden (#35)
- ✅ WSL audio: PortAudio ALSA/JACK cascade silenced at TTS init (#133)
- ⏳ Logging architecture: agent log volume mounts to host are stale —
  tracked under M15 (forge logging architecture).

### M1 fully shipped (2026-04-26)

ROADMAP "Shipped" entry has the canonical record. M2 and M9 are now
unblocked. Next smoke recipe (Round 7) lands as part of M13 — see
`plans/2026-04-26-forge-order-confirmation.md`.

## Round 7 — Forge Order Confirmation + HOTL ambiguity (10 min) — poster artifact

Validates the M13 confirmation gate end-to-end across the three tiers,
with intentionally chosen prompts to exercise each. This run is the
photographable evidence for the conference poster's HOTL claim — gives
the architectural-invariant story ("Kourai has a guaranteed Confirmation
Gate before any code generation") concrete terminal output to point at.

### Tier 1 (clear) — should produce a tight read-back

- [ ] **Terminal A:** `make up` — wait for "all agents ready"
- [ ] **Terminal B:** `make cli` — wait for REPL prompt
- [ ] `/project use hello-forge`
- [ ] Send: `add a function quadruple(n) that returns n*4 and a passing test`
- [ ] Expected: Hephaestus emits `CONFIRM_ORDER tier=clear` rendered as
      a Hephaestus comms window (🔥 prefix + italicized read-back per
      M10). Read-back ≤15 words, ends with "Light the forge?" or
      equivalent.
- [ ] Press Enter (or type `yes` / `go`) to confirm.
- [ ] Pipeline runs (Metis → Techne → Dokimasia → Kallos → Mneme).
- [ ] `/project accept` → ff-merge succeeds, `quadruple()` lands on main.

### Tier 2 (smart) — should surface Metis's suggested upsells

- [ ] Send: `add a divide function`
- [ ] Expected: `CONFIRM_ORDER tier=smart` — read-back mentions Metis's
      concerns (zero-division handling, type coercion) plus the
      `(Metis is muttering — say the word.)` hint suffix.
- [ ] Reply with one of the suggested options ("works" / "bare").
      Pipeline runs.

### Tier 3 (clarify) — should ask a specific clarifying question

- [ ] Send: `make my codebase faster`
- [ ] Expected: `CONFIRM_ORDER tier=clarify` — ONE specific
      missing-info question (e.g., "which functions?", "got
      benchmarks?") plus the `(Forge cools while we sort this out.)`
      hint suffix.
- [ ] Answer the question. Pipeline runs against your answer.

### `/yolo` opt-out

- [ ] `/yolo` → confirm the "ON — confirmation gate bypassed" message.
- [ ] Send a fresh tier-1 prompt — confirm the pipeline starts
      immediately with NO confirmation card (proves opt-out works).
- [ ] `/yolo` again → "OFF — confirmation gate active". Next prompt
      must gate again.

### Verification

- [ ] All three runs produced a `CONFIRM_ORDER` turn (no pipeline
      started without one — except in `/yolo` mode).
- [ ] Tier classifications match the prompt's actual ambiguity.
- [ ] No banned phrases (per `tests/integration/test_confirmation_voice.py`'s
      `BANNED_PHRASES` list — Hephaestus never roasts the player).
- [ ] Save the terminal output as
      `assets/poster/forge-order-tier-{1,2,3}.txt` for the poster figure.

---

## Done criteria

All of the above checked → ship it. File a follow-up issue for anything weird I'd
want to know about (especially: streaming UI glitches around the `⚒ Forging` line,
or session IDs that look ugly in the prompt).

## If something breaks

Tell me which step number, paste the output. The fix is almost certainly in one of:
- `hosts/cli/commands.py` (`_handle_project_command`)
- `hosts/cli/__main__.py` (REPL wrapper that injects `[project_root: …]`)
- `shared/src/kourai_common/forge_session.py` (worktree mgmt)
- `shared/src/kourai_common/sandbox.py` (container argv)
