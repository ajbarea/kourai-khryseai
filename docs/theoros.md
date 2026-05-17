# Theoros

From θεωρός — the "state-appointed spectator who watches a divine spectacle on behalf of the polis and reports back." Etymological ancestor of *theater* and *theory*.

In a theoros session: **Claude drives the REPL; you spectate read-only.** Your eyes and ears judge aesthetic concerns (does it sound right, does it feel right). Claude's queries judge operational concerns (did the request fire, did the log line emit).

## Role split

| Aesthetic (your eyes/ears) | Operational (Claude via logs) |
|---|---|
| Does Metis's voice sound natural? | Did Metis receive the request? |
| Does recall narration feel earned? | Did `narration emitted` fire? |
| Does audio crackle or clip? | What sample rate did pygame init at? |
| Does the comms-window layout look right? | What was the box width and content length? |
| Does the chat feel coherent across turns? | What did Hephaestus's user-message body contain? |

The split is committed to `.claude/skill-context.md`'s `## theoros` section so Claude reads it on every invocation. Memory rot does not apply.

## Starting a session

Make sure the core stack is up:

```bash
make up
```

Start the theoros session:

```bash
make theoros
```

Output tells you how to spectate from another terminal:

```bash
tmux attach -t kourai-theoros -r
```

The `-r` flag is read-only. Drop it if you want to take the wheel mid-session — both panes accept input from any attached client, so you can interject without restarting.

Claude drives via `tmux send-keys -t kourai-theoros:0.0 '<text>' Enter` and reads via `tmux capture-pane -t kourai-theoros:0.0 -p -S -<n>`. The bottom pane multiplexes `docker compose logs -f --tail 0 metis mneme hephaestus` (curated subset; adjust per session in `.claude/skill-context.md`).

## Aesthetic vs operational

The hard rule: anything that requires your ears, eyes, or taste is yours. Anything that can be expressed as a log query or a pane capture is Claude's. If Claude asks you to paste output, that is a regression on the discipline — say so.

The full discipline rules live in the `techne:theoros` skill body (`techne/plugins/techne/skills/theoros/SKILL.md`); the skill loads on every theoros invocation.

## Tear down

```bash
make theoros-down
```

Kills the tmux session and removes `/tmp/kourai-theoros.state`. Tmux scrollback dies with the session — if you want post-mortem logs, opt in to `tmux pipe-pane` (see the techne:theoros skill).

## Troubleshooting

- **`Prerequisite failed: Core containers not running.`** — Run `make up` first; `docker compose ps --status running` must list the agent containers.
- **`theoros session 'kourai-theoros' already running`** — Either attach to the existing session (`tmux attach -t kourai-theoros -r`) or tear it down (`make theoros-down`) before starting fresh.
- **Attach shows an empty screen** — The REPL pane may have exited (e.g., `make cli` failed to start). Run `make theoros-status` to see the state file; check `docker compose logs` for the agent containers.
- **Logs in the bottom pane scroll too fast to read** — Capture-on-demand with `tmux capture-pane -t kourai-theoros:0.1 -p -S -2000 | grep <pattern>`. The pane is informational; grep is the truth.
