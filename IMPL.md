# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-20 · Working on: **M1 — Tool-use migration**

---

## M1 plan-of-record

End state: `parse_and_apply_fixes` is gone, all three specialists
(Techne, Dokimasia, Kallos) drive the agentic loop via provider tool-use
through LiteLLM, smoke runs identical to today (accept + discard) with
no regex parsing in the path.

### Step 1 — `chat_with_tools()` in `shared/src/kourai_common/llm.py` ✅ 2026-04-20

- [x] Add `chat_with_tools(agent_name, messages, tools, tool_handlers, max_iters=10, ...)`.
- [x] Loop: call LiteLLM with `tools=tools, tool_choice="auto"`.
- [x] When the response has tool_calls, execute the handler for each call,
      append `{"role": "tool", "tool_call_id": ..., "content": ...}` messages,
      re-call.
- [x] Stop when no tool_calls in the response, or when `max_iters` is hit.
- [x] Return the final assistant text plus a handler call log (for tracing).
- [x] `handler_context` (server-trusted) overrides model-supplied args so the
      model can't hijack `project_root`.
- [x] 9 unit tests cover happy path, max_iters cap, unknown tool, handler
      exception, invalid JSON, callback hook, timeout, and context override.

Note: LiteLLM normalizes Anthropic `tool_use` into OpenAI-style
`message.tool_calls` with `function.name` + `function.arguments` (JSON string).
We use that shape end-to-end. `_normalize_tool_calls()` accepts either
attribute-style or dict-style entries to stay forward-compatible.

Reference: [How tool use works](https://docs.claude.com/en/docs/agents-and-tools/tool-use/how-tool-use-works).

### Step 2 — Forge tool registry (`shared/src/kourai_common/forge_tools.py`) ✅ 2026-04-20

- [x] `FORGE_TOOL_SCHEMAS` — OpenAI-style schemas LiteLLM normalizes for
      Anthropic, OpenAI, and Gemini. `additionalProperties: false` on each
      so the model can't sneak extra fields past us.
- [x] `FORGE_TOOL_HANDLERS` — async functions with `*, project_root` kw-only
      so the chat_with_tools handler_context injection is unambiguous.
- [x] Path safety mirrors `_resolve_safe_path`:
      `_translate_to_container` then `validate_file_path`. Failures return
      `"ERROR: ..."` strings (never raise) so the model can recover.
- [x] `edit_file` rejects 0-match AND >1-match (the old regex silently
      succeeded with 0 matches — that's the whole bug we're killing).
- [x] 20 unit tests: schema shape (3) + happy/escape/extension per tool +
      edge cases (no match, multi-match, missing file, empty no-op).

### Step 3 — Migrate Techne ✅ 2026-04-20

- [x] `agents/techne/agent.py`: dropped `generate_code()` and
      `generate_code_stream()`; added `apply_code_changes()` returning
      `(text, tool_log)`. Removed the entire ACTION/FILE/CONTENT instruction
      block from `SYSTEM_PROMPT`, replaced with brief tool-use guidance.
- [x] `agents/techne/agent_executor.py`: drives the tool loop, counts
      successful mutating calls (`write_file`/`edit_file`/`delete_file`)
      for the artifact's `files_changed` field, attaches the full
      `tool_calls` log to the DataPart for traceability. Per-call
      `working_status` updates in place of the old prose-chunking.
- [x] `tests/unit/test_techne.py`: replaced `TestGenerateCode`/
      `TestGenerateCodeStream` with `TestApplyCodeChanges` (4 tests covering
      tool wiring, file-context inclusion, image_parts, callback forwarding).
      Updated system-prompt assertions for the new tool-use guidance.
- [x] `tests/unit/test_executors.py::TestTechneExecutor`: now patches
      `apply_code_changes` returning `(text, tool_log)`.

### Step 4 — Migrate Dokimasia and Kallos ✅ 2026-04-20

- [x] Kallos `agent.py`: replaced `fix_lint_issues()` with
      `apply_lint_fixes(lint_output, file_paths, project_root, context_id)`
      driving `chat_with_tools` over `FORGE_TOOL_*`. Returns count of
      successful disk writes via `count_successful_writes()`.
- [x] Kallos `agent_executor.py`: drops `parse_and_apply_fixes`; wraps the
      new helper in an async `_apply_fixes` for the new `fix_loop` signature.
- [x] Dokimasia `agent.py`: replaced `fix_test_issues()` with
      `apply_test_fixes()` (same shape as Kallos's). `generate_tests_stream`
      stays as-is — it only displays text, doesn't write to disk.
- [x] Dokimasia `agent_executor.py`: same wrapper treatment.
- [x] Both specialists' SYSTEM_PROMPTs lose the FILE/ORIGINAL/REPLACEMENT
      block, replaced with brief TOOL USE guidance.
- [x] `fix_loop.run_fix_loop()` collapsed to a single async `apply_fixes`
      callback (was two: `fix_issues` + `apply_fixes`). The tool loop fuses
      LLM call and write into one agentic step, so the split is dead weight.
- [x] Full unit suite green: 2322 passed (skipped the about-to-be-deleted
      `test_parse_and_apply_fixes.py`).

### Step 5 — Retire `parse_and_apply_fixes` ✅ 2026-04-20

- [x] Deleted `parse_and_apply_fixes`, `_CREATE_PATTERN`, `_PATCH_PATTERN`,
      `_DELETE_PATTERN`, `_BOLD`, `_resolve_safe_path` from
      `shared/src/kourai_common/subprocess.py`. Dropped the `import re` and
      removed `parse_and_apply_fixes` from `__all__`.
- [x] Deleted `tests/unit/test_parse_and_apply_fixes.py`.
- [x] `grep parse_and_apply_fixes` returns zero hits in source — only
      `IMPL.md` and `ROADMAP.md` mention it (as the thing we just retired).

### Step 6 — Smoke (queued for next interactive `/project` session)

Live smoke needs the agent stack up and a human at the REPL — the assertions
are spelled out as **Round 6** in [SMOKE_TODO.md](./SMOKE_TODO.md). Summary:

- [ ] Round 6a (accept): drive a fresh forge → assert `tool_use write_file`/
      `edit_file` lines in `logs/dev-latest.log` and zero `parse_and_apply_fixes`
      lines, then `/project accept` and confirm the commit lands on main.
- [ ] Round 6b (discard): drive a fresh forge → `/project discard` → assert no
      zombies and main untouched.
- [ ] Compare wall-clock to v2 baseline (462 s) — should be ≤ baseline since
      we strip a regex pass.

Code-side this is the end of M1: 2322 unit tests green, `parse_and_apply_fixes`
is gone, all three specialists drive `chat_with_tools`. Only the live-stack
sanity check is left.

---

## Notes / open questions

- **LiteLLM tool-use shape — verify on live providers.** Unit tests use the
  OpenAI-style normalization (`function.name` + `function.arguments` JSON
  string + `tool_call_id`) and `_normalize_tool_calls()` accepts both
  attribute- and dict-style entries. Round 6 smoke is what proves Anthropic,
  OpenAI, and Gemini all actually emit that shape end-to-end through LiteLLM
  1.x — if any provider drops `tool_call.id` or returns a different
  envelope, a thin adapter goes here.

- **Ollama / local models without tool-use:** none currently in
  `get_model()` defaults, so we shipped without a fallback. If a local
  model without function-calling shows up later, add a guard in the
  specialist's `apply_*` helper that detects the missing capability and
  routes to a degraded path — don't resurrect `parse_and_apply_fixes`,
  ask the user instead.

- **Specialist transcripts:** the dev log now captures `tool_use <name>
  args=… result=…` at debug (`shared/src/kourai_common/llm.py:440`). For
  Round 6, also confirm `dev_log` sessions contain the assistant text plus
  the tool_call log so the full agentic round is replayable from disk.

- **M4 (prompt caching) — shipped 2026-04-26, with a correction.** The
  hand-off note above had the prompt sizes badly wrong: actual measurements
  on 2026-04-26 came in at Techne 1101 tokens / Kallos 1022 / Dokimasia
  1035 / Metis 913 / Hephaestus routing 632 — well below Sonnet 4.6 (2048)
  and far below Opus 4.6/4.7 (4096). Persona enrichment only adds ~240
  tokens in a typical mid-game profile, nowhere near closing the gap. So
  cross-call caching of the system prompt isn't paying off today, and
  bundling persona wouldn't have changed that.

  What we *did* ship is **within-loop caching** in `chat_with_tools`: the
  `[system + tools + initial-user]` prefix is reused across every
  iteration of the agentic loop, and the initial user message routinely
  carries 2K–10K tokens of `file_contents` + `git_context` + docs lookup.
  That combined prefix easily crosses 2048 (Sonnet) and frequently
  crosses 4096 (Opus), so iterations 2–N of every Techne / Kallos /
  Dokimasia run pay 10% of input price for the prefix instead of 100%.
  `chat` and `chat_stream` mark the system block too — sub-threshold
  prefixes are silently ignored by Anthropic at no cost, so the marker
  is free insurance once any agent's context grows.
  `cache_read_input_tokens` / `cache_creation_input_tokens` get
  debug-logged after every call so Round 6 can confirm hits in
  `dev-latest.log`.

---

## Up next (queued, not yet active)

- **M2** (`kourai-forge-mcp` server) — start once M1 ships and we've felt
  whether the toolset is right.
