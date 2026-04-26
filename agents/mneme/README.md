# Mneme — Commit Message Specialist

> Greek Μνήμη, "memory / remembrance." Reads the cumulative git diff
> after the pipeline finishes and produces structured commit message
> groups in AJ's exact format.

## Responsibility

Mneme is the last specialist in the standard "implement X" pipeline.
She reads the git status + diff that Hephaestus auto-collects after
all prior agents have written to disk, groups files logically, and
emits commit messages following the project's format conventions:
`type(scope): present-tense headline` plus past-tense bullets and
a `Files: …` line per group.

## A2A surface

| Field | Value |
|---|---|
| Port | `10005` |
| Skill ID | `commit_messages` |
| Streaming | Yes — chunked commit-message generation via `generate_commit_messages_stream` |
| `INPUT_REQUIRED` | No — Mneme is purely consumption + emission |
| Project root | Implicit (the `git diff` is collected by Hephaestus before the message reaches her) |
| Image attachments | No |

**Output artifact** — `commit_messages` with a `TextPart` carrying
the commit groups. The Forge Memoir layer (the per-session JSONL
log under `.kourai/memoir/`) extracts the same groups for downstream
consumption (PR creation, etc.).

## Tools

Mneme does NOT drive `chat_with_tools` — her output is prose, not
file ops. She uses `chat_stream()` only. She has GitHub PR-creation
helpers (`create_github_pr`, `github_create_pull_request_impl`) for
HOTL-confirmed PR ship paths, but the pipeline doesn't auto-invoke
them.

## Pipeline neighbors

- **Routes from:** Hephaestus (always last in any pipeline that
  modified files).
- **Routes to:** Hephaestus (returns artifact; pipeline ends).
- **Auto-collected context:** Hephaestus runs `collect_git_changes`
  (in `scripts/git_changes.py`) right before invoking Mneme and
  appends the result as `[Git Diff]: <output>` to the transcript.

## Key files

- `agent.py` — `SYSTEM_PROMPT` (scribe persona + format rules),
  `generate_commit_messages()` and `_stream` variants,
  `parse_commits_for_pr()` (extracts PR title/body),
  `create_github_pr()` (HOTL choice event for confirmation),
  `github_create_pull_request_impl()` (the actual PyGithub call).
- `agent_executor.py` — A2A bridge. Streams chunks back as
  `working_status` events.
- `__main__.py` — server entrypoint and AgentCard registration.

## Smoke recipe

```bash
make up
make cli
> /project use hello-forge
> commit prep
```

**What to expect.** Mneme streams `📜 reading git diff…` then a
sequence of commit-group blocks. Final artifact is the full
formatted commit-message list, ready to copy into `git commit`.

## Persona notes

Mneme is scholarly, meticulous, and remembers everything (literally).
She sasses Hephaestus about his poor documentation but chronicles
everything for the player. Warmth scales with affinity — at low
tiers she's a precise, impersonal recorder; at high tiers she
references past commits fondly and waxes poetic about a
well-structured changeset. See the `personality_baseline` block in
`agent.py::SYSTEM_PROMPT`.
