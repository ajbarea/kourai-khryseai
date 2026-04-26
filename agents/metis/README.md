# Metis — Planning Specialist

> Greek Μῆτις, "wise counsel." Transforms rough player ideas into
> implementable specifications: file lists, steps, edge cases,
> acceptance criteria.

## Responsibility

Metis is the first specialist Hephaestus calls for any "implement X"
or "plan X" request. She reads the existing code for context, fetches
relevant external documentation via Context7 MCP, and produces a
structured spec that downstream agents (Techne, Dokimasia) consume
verbatim. Her output is the contract for the rest of the pipeline.

## A2A surface

| Field | Value |
|---|---|
| Port | `10001` |
| Skill ID | `planning` |
| Streaming | Yes — chunked spec generation via `create_spec_stream` |
| `INPUT_REQUIRED` | Yes — emits when scope is genuinely ambiguous |
| Project root | Optional (used to surface git status + project structure as context) |
| Image attachments | Yes — design mockups, screenshots, etc. ride as `image_url` parts |

**Output artifact** — `spec` with a `TextPart` carrying the structured
spec (Summary / Files to Modify / Files to Create / Implementation
Steps / Acceptance Criteria / Edge Cases / Testing Notes). No
`DataPart` today — downstream agents parse the markdown.

## Tools

Metis drives `chat_stream()` (not `chat_with_tools`) — her output is
prose, not file ops. The Context7 documentation lookup happens via
`kourai_common.doc_lookup.lookup_documentation(idea, agent_name="metis")`
which is an MCP call routed through `MCPToolkit`.

## Pipeline neighbors

- **Routes from:** Hephaestus (default first step in any
  "implement X" template).
- **Routes to:** Hephaestus (returns spec; orchestrator hands it to
  Techne next).
- **Co-agent:** Techne reads Metis's spec verbatim as the
  user-message body for code generation.

## Key files

- `agent.py` — `SYSTEM_PROMPT` (planner persona + output-format
  rules), `get_project_context()` (git + tree snapshot),
  `create_spec()` and `create_spec_stream()` (the LLM calls), plus
  GitHub issue search.
- `agent_executor.py` — A2A bridge. Streams chunks back as
  `working_status` events so the player sees the spec being written
  rather than waiting for a black-box final blob.
- `__main__.py` — server entrypoint and AgentCard registration.

## Smoke recipe

```bash
make up
make cli
> @metis plan a CSV exporter that streams chunked I/O for files >100MB
```

**What to expect.** Metis emits a `📐 analyzing requirements…` status,
then chunked text as she writes the spec. If she needs clarification
("Should this stream by row or by chunk size?") she emits an
`INPUT_REQUIRED:` event and pauses for player input.

## Persona notes

Metis is strategic, elegant, and slightly smug about her intelligence.
She sasses Hephaestus and flirts with the player. Her warmth scales
with affinity — at low tiers she's precise and formal; at high tiers
she shares strategic insights like inside jokes. See the
`personality_baseline` block in `agent.py::SYSTEM_PROMPT`.
