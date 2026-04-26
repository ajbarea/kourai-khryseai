# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **M3 — A2A streaming task events**

---

## M3 plan-of-record

End state: every specialist that drives `chat_with_tools` (Techne,
Kallos, Dokimasia) emits one `TaskStatusUpdateEvent` per tool call so
the player sees `kallos: edit_file src/foo.py (ok)` land live during
the lint-fix loop instead of staring at a black box for a minute.

The protocol stack was already wired (Techne shipped this in M1):

- `chat_with_tools` invokes `on_tool_call(name, args, result)` once per
  successful tool execution (`shared/src/kourai_common/llm.py:555`).
- Hephaestus's `RemoteAgentConnection.send()` consumes
  `TaskStatusUpdateEvent`s from the SSE stream and yields them as
  `("status", text)` tuples (`agents/hephaestus/remote_connections.py:159`).
- `execute_pipeline` forwards the tuples to the host
  (`agents/hephaestus/agent.py:489`).
- The CLI's `_maidenify_status` renders each into a comms window in
  real time (`hosts/cli/events.py:86`).

What was missing: Kallos's `apply_lint_fixes` and Dokimasia's
`apply_test_fixes` swallowed the LLM tool-loop entirely — no
`on_tool_call` parameter, no callback wiring in the executor.

### Step 1 — Surface `on_tool_call` on Kallos's apply_lint_fixes ✅ 2026-04-26

- [x] `agents/kallos/agent.py::apply_lint_fixes`: added
      `on_tool_call: Callable[[str, dict, str], Awaitable[None]] | None`
      parameter, default `None`, forwarded to `chat_with_tools` verbatim.
      Mirrors Techne's `apply_code_changes` signature so the executor
      pattern is identical.

### Step 2 — Same surface on Dokimasia's apply_test_fixes ✅ 2026-04-26

- [x] `agents/dokimasia/agent.py::apply_test_fixes`: same parameter,
      same default, same forwarding shape.

### Step 3 — Kallos executor wires `_on_tool` ✅ 2026-04-26

- [x] `agents/kallos/agent_executor.py`: added an `_on_tool` closure
      mirroring Techne's wrench-style status (`f"{name} {target}
      ({ok|fail})"`) but with Kallos's signature emoji `✨`. The
      closure is passed via the `_apply_fixes` wrapper so `run_fix_loop`
      threads it through transparently.

### Step 4 — Dokimasia executor wires `_on_tool` ✅ 2026-04-26

- [x] `agents/dokimasia/agent_executor.py`: same pattern with
      Dokimasia's `🧪`. Wired only in the `is_run_request` branch —
      the test-generation branch doesn't drive `chat_with_tools` so it
      doesn't need the callback.

### Step 5 — Tests ✅ 2026-04-26

- [x] `tests/unit/test_tool_call_streaming.py`: 7 tests across 5 classes:
      `TestApplyLintFixesForwardsCallback` (2), `TestApplyTestFixesForwardsCallback`
      (2) — boundary tests verifying the callback reaches `chat_with_tools`
      with both an explicit value and the default `None`. Then
      `TestKallosExecutorEmitsToolCallStatus`, `TestDokimasiaExecutorEmitsToolCallStatus`,
      and `TestErrorTagInToolMessage` (1 each) drive the executors with
      a fake `run_fix_loop` that synthesises a tool execution and
      asserts `send_working_status` was called with the right emoji and
      `(ok)` / `(fail)` suffix. Suite runs in 2.82 s.

### Step 6 — Live smoke (queued for next interactive `/project` session)

- [ ] Send `@kallos` task that triggers a non-trivial lint fix → confirm
      multiple `✨ edit_file <path> (ok)` lines stream during the fix
      loop instead of one big silence.
- [ ] Send `@dokimasia run tests` against a failing suite → confirm
      `🧪 write_file tests/test_x.py (ok)` lines appear during the
      auto-fix iteration.
- [ ] Compare the perceived stage latency between Techne (already
      streamed) and the newly streamed Kallos/Dokimasia — they should
      feel the same now.

---

## Notes / open questions

- **Per-tool emoji vs per-maiden emoji.** Techne uses `🔧` (wrench) for
  her tool-call status, distinct from her own `⚙️`. Kallos and
  Dokimasia ship with their signature emojis (`✨` and `🧪`) since
  the comms-window header already names the maiden — duplicating the
  wrench across all three would obscure attribution in the CLI's
  emoji-driven `_maidenify_status` detector. If we ever add a
  generic "agent did a tool call" detector, revisit.

- **Streaming subprocess output is unchanged.** Kallos's `_lint_status`
  callback still forwards each ruff/ty stdout line to
  `send_working_status` with `💻`. Dokimasia's `_pytest_status` does
  the same with `🧪`. Those are subprocess-streaming, separate from
  the new LLM-tool-call streaming. Both flows now yield events; the
  player sees a much busier (in a good way) status stream during the
  fix loop.

- **The `(ok)` / `(fail)` suffix.** Forge tools return `"ERROR: ..."`
  on path-safety violations and similar guards. The `_on_tool` closure
  prefix-checks the result and renders `(fail)` in that case. Saves the
  player from squinting at the actual error string in the comms stream
  — they get the actual error in the final artifact text after the
  loop completes.

---

## Up next (queued, not yet active)

- **M2** (`kourai-forge-mcp` server) — gated on M1 Round 6 smoke
  (the toolset-feel check needs the live REPL).
- **M11** (GUI attachment send path) — closes the CLI/GUI multimodal
  asymmetry; Alt+V capture works but the captured image never reaches
  Hephaestus today. Concrete done criteria, no blockers.
- **M9** (Opus 4.6 → 4.7 in `MODELS_SMART["metis"]`) — one-line bump,
  also wants Round 6 smoke first.
