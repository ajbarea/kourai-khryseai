# Dokimasia — Testing Specialist

> Greek δοκιμασία, "trial / examination." Writes pytest suites for new
> code and runs them; on failure, drives the agentic tool-use loop to
> fix tests or the code under test.

## Responsibility

Dokimasia is the second specialist in the standard "implement X"
pipeline (after Techne). Her two modes are decided by keyword in
the user message:

1. **Generate tests** (default) — writes pytest for the module
   Techne just touched, streams the test code as it's written.
2. **Run tests** (`run tests`, `make test`, `pytest`, `run all`) —
   executes the test suite via subprocess, streams pytest output
   line-by-line, drives a fix loop on failure.

## A2A surface

| Field | Value |
|---|---|
| Port | `10003` |
| Skill IDs | `write_tests`, `run_tests` |
| Streaming | Yes — pytest output line-by-line + per-tool-call events during fix loop |
| `INPUT_REQUIRED` | Rare — emits if the failing test surface is ambiguous |
| Project root | Required (pytest runs against the project's worktree) |
| Image attachments | Yes — screenshots feed into test generation as visual context for the LLM |

**Output artifact** — `test_results` (run-mode) or `generated_tests`
(write-mode), each with a `TextPart` carrying the human-readable
summary and (for run-mode) a `DataPart` with the structured
`PytestRunResult` fields.

## Tools

In **fix-loop mode** Dokimasia drives `chat_with_tools` with the
same forge tool set (`read_file`, `write_file`, `edit_file`,
`delete_file`) — each tool call streams a `🧪 <name> <path>
(ok|fail)` status event. In **write-mode** she uses `chat_stream()`
only (output is test code, not file ops; the executor saves the
chunked output as the artifact directly).

## Pipeline neighbors

- **Routes from:** Hephaestus (after Techne in the standard
  "implement X" pipeline).
- **Routes to:** Hephaestus (returns artifact; orchestrator usually
  hands off to Kallos next).
- **Loops with:** Itself — the fix loop iterates up to
  `MAX_ITERATIONS` times when pytest fails.

## Key files

- `agent.py` — `SYSTEM_PROMPT` (tester persona + output-format
  rules), `run_pytest()` (subprocess driver),
  `apply_test_fixes()` (agentic tool loop),
  `generate_tests_stream()`.
- `agent_executor.py` — A2A bridge. Two branches on user-input
  keywords (run vs. generate); wires `_on_tool` for live status
  during the fix loop.
- `__main__.py` — server entrypoint and AgentCard registration.

## Smoke recipe

```bash
make up
make cli
> @dokimasia run tests in tests/unit/
```

**What to expect.** Dokimasia streams `🧪 <pytest line>` events as
the suite runs. On failure she emits `🧪 write_file <path> (ok)`
events as the fix loop applies edits. Final artifact carries the
pytest summary and full output (truncated to last 2K chars).

## Persona notes

Dokimasia is fierce, thorough, and protective of code quality. She
sasses Hephaestus but protects the player's code. Warmth scales
with affinity — at low tiers she's curt; at high tiers she
celebrates victories together and shows genuine concern when tests
reveal real bugs. See the `personality_baseline` block in
`agent.py::SYSTEM_PROMPT`.
