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

| Command | Action |
|---|---|
| `:q` or `quit` or `exit` | Exit the CLI |
| `:status` | Show agent name, version, URL, context ID, streaming status |
| `:help` | Show command help |
| `:maidens` | Meet the Golden Maidens (list all agents) |
| `:maidens <name>` | Show a specific maiden by name |
| `:copy` | Copy last result to clipboard |
| `:save <file>` | Save last result to a file |
| `:clear` | Clear the screen |
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
Type your request. Commands: :q (quit), :status (agent info)

Connecting to Hephaestus at http://localhost:10000/...
Connected to Hephaestus — Orchestrator v0.1.0
Skills: Route Development Request, Execute Development Pipeline

kourai: fix the off-by-one error in pagination

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
kourai: refactor the data layer

🔥 Hephaestus: Request needs clarification
↳ Your response: Which specific module? The ORM layer, the API clients, or the caching layer?
```

Type your response and the pipeline continues. Type `:q` to abort.

---

## Context Persistence

The CLI maintains a `context_id` across requests within a session. This means follow-up requests can reference previous context:

```
kourai: plan a user authentication system
...
kourai: implement it
...
kourai: add tests for it
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
