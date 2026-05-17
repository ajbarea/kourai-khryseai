# Theoros

An observed live REPL session. Claude drives `make cli` via `tmux send-keys`; you spectate read-only via `tmux attach -t kourai-theoros -r`. Named after θεωρός — the Greek "state-appointed spectator sent by the polis to watch the sacred games and report back what was worth knowing." Ancestor of *theater* and *theory*.

**Script:** `scripts/theoros.sh`  
**Skill:** `techne:theoros`  
**State file:** `/tmp/kourai-theoros.state`

---

## Role split

The whole point of theoros is that **two actors** are watching the session, and each has a different job:

| Aesthetic (your eyes/ears) | Operational (Claude via logs) |
|---|---|
| Does Metis's voice sound natural? | Did Metis receive the request? |
| Does recall narration feel earned? | Did `narration emitted` fire? |
| Does audio crackle or clip? | What sample rate did pygame init at? |
| Does the comms-window layout look right? | What was the box width and content length? |
| Does the chat feel coherent across turns? | What did Hephaestus's user-message body contain? |

The split is committed to `.claude/skill-context.md`'s `## theoros` section so the `techne:theoros` skill loads it on every invocation. Memory rot doesn't apply.

**Hard rule:** if Claude asks you to paste log output, that's a regression on the role split — say so. The full discipline lives in the `techne:theoros` skill body.

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
theoros session ready.
  Spectate:   tmux attach -t kourai-theoros -r
  Take over:  tmux attach -t kourai-theoros
  Tear down:  make theoros-down
```

Attach from another terminal (or pane) with `-r`. Drop the `-r` to take the wheel — both panes accept input from any attached client, so you can interject without restarting.

---

## What's in the session

A single tmux session, `kourai-theoros`, with two panes:

| Pane | Index | What runs there |
|---|---|---|
| **Top (60%)** | `kourai-theoros:0.0` | `make cli` — the interactive REPL Claude drives via `tmux send-keys` |
| **Bottom (40%)** | `kourai-theoros:0.1` | `docker compose logs -f --tail 0 metis mneme hephaestus` — native multi-service tail with built-in service-name prefixes |

The agent list in the bottom pane is curated, not exhaustive — edit `ops_command:` in `.claude/skill-context.md` to tail different agents per session. The full agent set is `metis mneme kallos dokimasia puck cupid aidos aletheia hephaestus vn-bridge`.

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
  "ops_pane": "kourai-theoros:0.1"
}
```

`tmux has-session -t kourai-theoros` is the live source of truth; the state file carries metadata the `techne:theoros` skill reads across Claude's turns.

---

## Tear down

```bash
make theoros-down
```

Kills the tmux session and removes `/tmp/kourai-theoros.state`. Tmux scrollback dies with the session — if you want post-mortem logs to survive `down`, the `techne:theoros` skill documents an opt-in `tmux pipe-pane` mode.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ERROR: Prerequisite failed: Core containers not running.` | Stack isn't up | `make up` first |
| `theoros session 'kourai-theoros' already running` | Session left from a previous run | `make theoros-down` to start fresh, or attach with `-r` to the existing one |
| Top pane is blank or exited | `make cli` failed to start | Check `docker compose logs hephaestus` and `make status`; rerun `make theoros` after fixing |
| Bottom pane is empty or doesn't update | A service in `ops_command:` doesn't exist or isn't running | `docker compose ps` to verify; trim the list in `.claude/skill-context.md` |
| Bottom pane scrolls too fast to read | High-traffic agents | Capture-on-demand: `tmux capture-pane -t kourai-theoros:0.1 -p -S -2000 \| grep <pattern>` — grep is the truth, the pane is informational |
