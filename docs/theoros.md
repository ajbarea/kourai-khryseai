# Theoros

An observed live REPL session. By default `make theoros` runs in **autopilot mode**: a separate `claude` CLI session in a middle pane drives `make cli` (top pane) through a curated prompt library, while you attach with `tmux attach -t kourai-theoros -r` and watch all three panes — REPL, Claude's reasoning, docker logs. Named after θεωρός — the Greek "state-appointed spectator sent by the polis to watch the sacred games and report back what was worth knowing." Ancestor of *theater* and *theory*.

**Script:** `scripts/theoros.sh`  
**Driver brief:** `scripts/theoros_autopilot.md`  
**Prompt library:** `tests/fixtures/theoros_prompts.md`  
**Skill (manual mode):** `techne:theoros`  
**State file:** `/tmp/kourai-theoros.state`

---

## Role split

Two actors are watching the session, and each has a different job. The autopilot Claude in the middle pane covers the operational column; the human spectator covers the aesthetic column.

| Aesthetic (your eyes/ears) | Operational (autopilot Claude via logs) |
|---|---|
| Does Metis's voice sound natural? | Did Metis receive the request? |
| Does recall narration feel earned? | Did `narration emitted` fire? |
| Does audio crackle or clip? | What sample rate did pygame init at? |
| Does the comms-window layout look right? | What was the box width and content length? |
| Does the chat feel coherent across turns? | What did Hephaestus's user-message body contain? |

The split is committed to `.claude/skill-context.md`'s `## theoros` section and to the autopilot brief at `scripts/theoros_autopilot.md`.

**Hard rule:** if autopilot Claude asks you to paste log output, that's a regression on the role split — it should be capturing panes itself. The full discipline lives in the autopilot brief.

---

## Starting a session

The stack must already be running:

```bash
make up
```

Then start theoros:

```bash
make theoros
```

Output prints the spectator command:

```
theoros session ready (autopilot).
  Spectate:   tmux attach -t kourai-theoros -r
  Take over:  tmux attach -t kourai-theoros
  Tear down:  make theoros-down

Claude is driving the REPL via the middle pane. Watch all three:
  top    — kourai REPL (the game)
  middle — Claude's reasoning
  bottom — docker compose logs
```

Attach from another terminal with `-r` for safe spectating. Drop the `-r` to take the wheel mid-session — all panes accept input from any attached client.

---

## What's in the session

A single tmux session, `kourai-theoros`, with three panes:

| Pane | Index | What runs there |
|---|---|---|
| **Top (40%)** | `kourai-theoros:0.0` | `make cli` — the kourai REPL. Driven by autopilot via `tmux send-keys`. |
| **Middle (30%)** | `kourai-theoros:0.1` | `claude` CLI — autopilot Claude. Reads `scripts/theoros_autopilot.md`, works through the prompt library, narrates observations. |
| **Bottom (30%)** | `kourai-theoros:0.2` | `docker compose logs -f --tail 0 <agents>` — native multi-service tail. |

The agent list in the bottom pane is curated, not exhaustive — edit `ops_command:` in `.claude/skill-context.md` to tail different agents per session. The full agent set is `metis mneme kallos dokimasia puck cupid aidos aletheia hephaestus vn-bridge`.

The prompt library at `tests/fixtures/theoros_prompts.md` is a **golden dataset** (2026 best practice: curated, not random) of `(input, expected behavior, observable signal)` triples covering every CHAT route. v1 covers 12 prompts; pipeline-triggering prompts are deferred to v2 (they take 5–20 minutes each and create forge sessions to clean up).

---

## Manual mode (`--no-autopilot`)

When the `techne:theoros` skill is invoked from inside a Claude Code conversation, Claude is already the driver — a second `claude` pane would be redundant. The skill invokes the script with `--no-autopilot`:

```bash
bash scripts/theoros.sh up --no-autopilot
```

This gives the 2-pane layout (REPL top 60%, ops bottom 40%) with no autopilot Claude in the middle. You drive the REPL yourself (or via the surrounding CC conversation).

---

## State

```bash
make theoros-status
```

Prints either the JSON state file or `No theoros session running.`:

```json
{
  "session": "kourai-theoros",
  "started_at": "2026-05-17T14:23:01Z",
  "cwd": "/home/ajbar/ajsoftworks/kourai-khryseai",
  "repl_pid": 12345,
  "attach_cmd": "tmux attach -t kourai-theoros -r",
  "driver_pane": "kourai-theoros:0.0",
  "autopilot_pane": "kourai-theoros:0.1",
  "ops_pane": "kourai-theoros:0.2",
  "autopilot": 1
}
```

When autopilot is off, `autopilot_pane` is `null` and `autopilot` is `0`. `ops_pane` shifts to `kourai-theoros:0.1` (the 2-pane layout uses 0.0 + 0.1).

---

## Tear down

```bash
make theoros-down
```

Kills the tmux session and removes `/tmp/kourai-theoros.state`. Tmux scrollback dies with the session.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ERROR: Autopilot requires the 'claude' CLI on PATH.` | Claude Code not installed | Install per https://docs.claude.com/code, or run `bash scripts/theoros.sh up --no-autopilot` for the 2-pane manual flow |
| `ERROR: Prerequisite failed: Core containers not running.` | Stack isn't up | `make up` first |
| `theoros session 'kourai-theoros' already running` | Session left from a previous run | `make theoros-down` to start fresh, or attach with `-r` to the existing one |
| Top pane is blank or exited | `make cli` failed to start | Check `docker compose logs hephaestus` and `make status`; rerun `make theoros` after fixing |
| Middle pane shows `claude` welcome but no driving | Autopilot brief read failed, or claude misinterpreted the bootstrap message | Read the brief manually in the middle pane: "Read scripts/theoros_autopilot.md and execute its instructions." |
| Bottom pane is empty or doesn't update | A service in `ops_command:` doesn't exist or isn't running | `docker compose ps` to verify; trim the list in `.claude/skill-context.md` |
| Bottom pane scrolls too fast to read | High-traffic agents | Capture-on-demand: `tmux capture-pane -t kourai-theoros:0.2 -p -S -2000 \| grep <pattern>` — grep is the truth, the pane is informational |
