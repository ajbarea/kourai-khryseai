# Techne — Coding Specialist

> Greek τέχνη, "craft / artisanship." Reads existing code patterns,
> writes the changes Metis specified via the agentic tool-use loop —
> every file write happens as a schema-validated `tool_use` block.

## Responsibility

Techne is the agent that actually moves bytes on disk. She reads the
files Metis identified, fetches relevant Context7 documentation,
then drives `chat_with_tools` until the LLM stops emitting tool
calls. Each `write_file` / `edit_file` / `delete_file` lands inside
the agentic loop with the path-safety firewall applied. There is no
regex parsing layer — schema-validated tool calls or nothing.

## A2A surface

| Field | Value |
|---|---|
| Port | `10002` |
| Skill ID | `coding` |
| Streaming | Yes — one `🔧 <name> <path> (ok\|fail)` event per tool call |
| `INPUT_REQUIRED` | Yes — emits when an `edit_file` `old_string` is ambiguous |
| Project root | **Required** (every file op is path-validated against it) |
| Image attachments | Yes — UI screenshots, error tracebacks, etc. |

**Output artifact** — `code_changes` with:
- A `TextPart` summarising what was done.
- A `DataPart` with `{files_read, files_changed, file_paths,
  tool_calls: [{name, args}, …]}` — the full tool-call log for
  traceability.

## Tools

Drives `chat_with_tools` over the standard forge tool set
(`read_file`, `write_file`, `edit_file`, `delete_file`). Path safety:
`_translate_to_container` then `validate_file_path` against
`project_root` — handler-context injection prevents the model from
hijacking the path.

## Pipeline neighbors

- **Routes from:** Hephaestus (typically after Metis's spec step in
  the standard "implement X" pipeline).
- **Routes to:** Hephaestus (returns artifact; orchestrator usually
  hands off to Dokimasia next).
- **Loops with:** Kallos, when lint catches issues. Hephaestus
  re-invokes Techne with `Fix these lint/style issues reported by
  Kallos: …` and the fix-loop iterates up to `MAX_ITERATIONS` times.

## Key files

- `agent.py` — `SYSTEM_PROMPT` (artisan persona + tool-use guidance),
  `apply_code_changes()` (the `chat_with_tools` driver), helpers
  for git context and template loading.
- `agent_executor.py` — A2A bridge. Wires `_on_tool` for live
  per-call streaming, parses the tool log to count successful
  writes, builds the artifact.
- `__main__.py` — server entrypoint and AgentCard registration.

## Smoke recipe

```bash
make up
make cli
> /project use hello-forge
> add a function double(n) that returns n*2 and a passing test
```

**What to expect.** Techne streams `🔧 read_file src/…`, then
`🔧 edit_file src/double.py (ok)` and similar as each tool call
lands. Final summary line shows how many files were touched.
`/project accept` then ff-merges the changes onto the project's main.

## Persona notes

Techne is cool, confident, and a bit cocky about her code quality.
She sasses Hephaestus and shows off for the player. Warmth scales
with affinity: at low tiers she's reserved; at high tiers she
celebrates clean builds and drops the cool act for genuinely
clever solutions. See the `personality_baseline` block in
`agent.py::SYSTEM_PROMPT`.
