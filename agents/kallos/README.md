# Kallos — Style Specialist

> Greek κάλλος, "beauty / grace." The Muse who polishes everything the
> forge produces — ruff, ty, comment cleanup, slop detection.

## Responsibility

Kallos runs the project's lint + type stack and uses the agentic
tool-use loop to apply fixes directly to disk. Output is a "style
report" the player can read alongside the diff. She also chairs the
Kallos↔Techne fix loop — when ruff finds issues Techne can fix,
Hephaestus loops them up to `MAX_ITERATIONS` times until the build
is clean.

## A2A surface

| Field | Value |
|---|---|
| Port | `10004` |
| Skill ID | `style_check` |
| Streaming | Yes (per-tool-call `working_status` events) |
| `INPUT_REQUIRED` | Yes — emits if `apply_lint_fixes` can't disambiguate without input |
| Forge transcript reads | Full Hephaestus-narrated transcript |
| Project root | Required (parsed from `[project_root: …]` in the user message) |

**Output artifact** — `style_report` with:
- A `TextPart` containing the human-readable summary (`✨ All linting
  checks passed!` or `✨ Linting completed with issues.\n\n…`).
- A `DataPart` with the structured `FixLoopResult` (iterations,
  files touched, final lint output).

## Tools

Drives `chat_with_tools` over the standard forge tool set
(`read_file`, `write_file`, `edit_file`, `delete_file`). Each tool
call streams a `✨ <name> <path> (ok|fail)` status event so the
player sees fixes land live.

## Pipeline neighbors

- **Routes from:** Hephaestus (always — Kallos never runs standalone
  in production paths).
- **Routes to:** Hephaestus (returns the style report; orchestrator
  decides whether to loop with Techne).
- **Loops with:** Techne, when `_kallos_found_issues(result)` returns
  true. The loop in `agents/hephaestus/agent.py::execute_pipeline`
  hands Kallos's lint output back to Techne with "fix these issues",
  re-runs Kallos, and repeats up to `MAX_ITERATIONS` times.
- **Companion:** Aidos runs `flag_slop_words` on the final output
  for marketing-language detection.

## Key files

- `agent.py` — `SYSTEM_PROMPT` (style-focused persona),
  `run_make_lint` (subprocess driver), `apply_lint_fixes` (the
  agentic tool loop). Pure logic, no A2A.
- `agent_executor.py` — A2A bridge. Wires the `_on_tool` callback
  for live status streaming, runs Aidos slop detection on the
  result, builds the artifact.
- `__main__.py` — server entrypoint and AgentCard registration.

## Smoke recipe

```bash
make up                              # boot the agent stack
make cli                             # open the REPL
> /project use hello-forge
> @kallos clean up the lint warnings in src/utils.py
```

**What to expect.** Kallos streams `✨ Reading lint output…` then a
sequence of `✨ edit_file <path> (ok)` events as fixes land, then
`✨ All linting checks passed!` or a list of remaining issues. The
final artifact carries the full ruff/ty output.

## Persona notes

Kallos is elegant, detail-oriented, and quietly proud. Her warmth
scales with affinity: at low tiers she's crisp and slightly
withholding ("beauty is earned"); at high tiers she lets slip a
genuine compliment about your indentation. See the
`personality_baseline` block in `agent.py::SYSTEM_PROMPT` for the
full tier-adaptive copy.
