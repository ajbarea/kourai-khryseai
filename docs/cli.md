# CLI Reference

The Kourai Khryseai CLI is an interactive REPL that connects to Hephaestus and streams pipeline progress in real-time.

**Location:** `hosts/cli/__main__.py`

---

## Starting the CLI

```bash
make cli
```

Or directly:

```bash
uv run python -m hosts.cli
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--agent URL` | Auto-detected from config | Override the Hephaestus URL |
| `--timeout SECONDS` | `600` | Request timeout |
| `-v`, `--verbose` | Off | Show timing, event counts, and debug details |
| `-p`, `--prompt TEXT` | *(interactive)* | Run a single prompt non-interactively (headless mode) |
| `--voice` / `--no-voice` | *(saved setting)* | Override TTS on/off for this run. `--no-voice` for unattended runs (smoke driver, headless CI, WSL2 without an audio device) |
| `--demo` | Off | Scripted Hephaestus→Metis pause scene, no network, no LLM (for poster screenshots and recordings) |
| `--json` | Off | Emit one JSON record per agent event on stdout (JSON Lines). Use with `-p` for agent piping; mirrors OpenAI Codex `--json` and Claude Code `--output-format stream-json` |

```bash title="Examples"
# Connect to a specific Hephaestus instance
uv run python -m hosts.cli --agent http://192.168.1.50:10000/

# Verbose mode for debugging
uv run python -m hosts.cli --verbose

# Run a single prompt non-interactively
uv run python -m hosts.cli -p "commit prep"
```

---

## REPL Commands

Type `/` at an empty prompt to open the live-filtering slash menu — arrow keys
navigate, `Tab` or `Enter` accepts the highlighted entry.

| Command | Action |
|---|---|
| `/q`, `/quit`, `/exit` or `quit` | Exit the CLI |
| `/status` | Show agent name, version, URL, context ID, streaming status |
| `/help` | Show command help |
| `/settings` (alias `/config`) | Toggle voice, music, romance, and game systems |
| `/model [cheap\|standard\|smart]` | Show current provider/tier/model — or switch tier mid-session (no restart) |
| `/model_tier` | Alias for `/model` — kept for back-compat |
| `/metrics` | Show alignment, affinity, and virtue metrics |
| `/usage` (alias `/cost`) | Per-(agent, model) tokens + dollar cost for this session |
| `/reset_usage` | Zero the session usage counter |
| `/yolo` | Toggle the M13 CONFIRM_ORDER pre-pipeline gate (power-user opt-out) |
| `/permissions` | List gate flags; `/permissions <name>` toggles one (e.g. `auto_approve_reads`) |
| `/preferences` (alias `/prefs`) | Browse, override, or forget closed-vocab preference facts (M17 Phase 2) |
| `/compact` | Fold older transcript turns into long-term memory; cache stays warm |
| `/session` (or `/session show`) | Print active context, agents touched, message + token totals |
| `/session list` | List known context IDs in the message store (busiest first) |
| `/session fork` | Clone the current context to a new ID for branching exploration |
| `/session resume <id>` | Switch the active context to a prior ID (hex prefix accepted) |
| `/maidens` | Meet the Golden Maidens (list all agents) |
| `/maidens <name>` | Show a specific maiden by name |
| `/scratchpad` | List agents with buffered reasoning |
| `/scratchpad <agent>` | Show that agent's recent reasoning, oldest-first |
| `/scratchpad clear [<agent>]` | Clear all scratchpads, or just one agent's |
| `/project new <name> [--template …]` | Forge a new player project |
| `/project list` | List all your player projects |
| `/project use <name\|id>` | Select an active project |
| `/project current` | Show the active project |
| `/project clear` | Clear the active project |
| `/project status` | Show pending forge sessions on active project |
| `/project accept [session_id]` | Merge a forge session into main (latest if no id given) |
| `/project discard [session_id]` | Discard a forge session (latest if no id given) |
| `/project delete <name\|id> [--purge] [--yes]` | Delete a project from the registry (`--purge` removes worktrees, `--yes` skips confirmation) |
| `/copy` | Copy last result to clipboard |
| `/save [filename]` | Save last result to a file |
| `/clear` | Clear the screen |
| Any other text | Send as a request to Hephaestus |

---

## How Requests Work

When you type a request:

1. The CLI sends it to Hephaestus as an A2A `SendStreamingMessageRequest`
2. Hephaestus routes it to a pipeline of specialists
3. The CLI receives and displays events as they stream back:
    - **`TaskStatusUpdateEvent`** — Progress messages (agent name, step number, status)
    - **`TaskArtifactUpdateEvent`** — Final output (commit messages, test results, etc.)
4. The final artifact is displayed between separator lines

### Example Session

```
╔══════════════════════════════════════════╗
║     Kourai Khryseai — Golden Maidens     ║
╚══════════════════════════════════════════╝
Type your request. Commands: /q (quit), /status (agent info)

Connecting to Hephaestus at http://localhost:10000/...
Connected to Hephaestus — Orchestrator v0.1.0
Skills: Route Development Request, Execute Development Pipeline

❯ fix the off-by-one error in pagination

🔥 [1/4] Sending task to Techne...
⚙️ [1/4] Techne completed
🔥 [2/4] Sending task to Dokimasia...
🧪 [2/4] Dokimasia completed
🔥 [3/4] Sending task to Kallos...
✨ [3/4] Kallos completed
🔥 [4/4] Sending task to Mneme...
📜 [4/4] Mneme completed
🔥 Pipeline complete

────────────────────────────────────────
fix(pagination): correct off-by-one in page calculation
- Fixed page boundary calculation using ceiling division
- Updated corresponding test assertions
Files: src/api/pagination.py, tests/unit/test_pagination.py
────────────────────────────────────────
```

---

## Input Required

When an agent needs clarification, the CLI prompts you for a response:

```
❯ refactor the data layer

🔥 Hephaestus: "Request needs clarification."
↳ Your response: "Which specific module? The ORM layer, the API clients, or the caching layer?"
```

Type your response and the pipeline continues. Type `/q` to abort.

---

## Context Persistence

The CLI maintains a `context_id` across requests within a session. This means follow-up requests can reference previous context:

```
❯ plan a user authentication system
...
❯ implement it
...
❯ add tests for it
```

Each request in the same session shares the same conversation context.

---

## Verbose Mode

With `-v` / `--verbose`, the CLI shows additional diagnostics:

```
[verbose] Sending 42 chars, context=a1b2c3d4
🔥 [1/2] Sending task to Techne...
⚙️ [1/2] Techne completed
🔥 [2/2] Sending task to Mneme...
📜 [2/2] Mneme completed
[verbose] 8 events in 12.3s
```

Useful for debugging connection issues, slow responses, or unexpected routing.

---

## Error Handling

| Scenario | CLI behavior |
|---|---|
| Hephaestus unreachable at startup | Prints error, suggests `make up`, exits |
| Connection lost mid-request | Prints "Connection lost to Hephaestus", returns to prompt |
| Request timeout | Prints "Request timed out", returns to prompt |
| JSON-RPC error from agent | Prints the error, returns to prompt |

The CLI never crashes on transient errors — it always returns you to the prompt.
