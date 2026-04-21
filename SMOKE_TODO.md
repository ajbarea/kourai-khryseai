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

## Round 6 — M1 tool-use migration validation (5 min)

This validates the regex parser → provider tool-use swap in `chat_with_tools`.
Re-runs Round 1's accept path and Round 2's discard path with the new wiring.

- [ ] `make up` then `make cli` (host runner is fine; tool-use is provider-side
      and runner-agnostic)
- [ ] `/project use hello-forge`
- [ ] **Round 6a — accept**: send a fresh task, e.g. `add a function double(n) that
      returns n*2 and a passing test`
- [ ] After Hephaestus finishes streaming, grep the dev log:
      `grep -E 'tool_use (write_file|edit_file|delete_file)' logs/dev-latest.log`
  - Expected: at least one match (proves Techne actually called tools, not the
      old ACTION/FILE/CONTENT prose). Kallos/Dokimasia rounds may also show
      `edit_file` calls if they had to fix anything.
- [ ] **No** `parse_and_apply_fixes` lines in the log
      (`grep parse_and_apply_fixes logs/dev-latest.log` returns nothing).
- [ ] `/project status` → one active forge session
- [ ] `/project accept` → ff-merge succeeds, `git log -1` on main shows the
      `forge: <id> pipeline output` commit and `double()` lives in the project.
- [ ] **Round 6b — discard**: `/project use hello-forge`; send another task,
      e.g. `add a function triple(n) that returns n*3`. After streaming
      completes, `/project discard` (latest). Confirm:
  - `git log -1` on main is unchanged from 6a
  - no `triple.py` on disk
  - `forge/` branch for the discarded session is gone
- [ ] **Wall-clock check**: compare Round 6a's total duration (start of stream
      → "all complete") to the v2 baseline (462 s). Should be ≤ baseline since
      we removed a regex pass per round; faster is fine, slower needs a look.

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
