# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

## In flight

**M21 — Companion A2A routing (replace CHAT ventriloquy)**, branch
`m21-companion-a2a-routing`. Hephaestus's `CHAT:<agent>:` path used
to emit a router-glossed line through its own task updater with the
target's emoji — the companion's container was never invoked. Now
opens a real `RemoteAgentConnection` to the target, forwards its
status + final result back through Hephaestus's updater, and falls
back to a Hephaestus-voiced apology if the companion is unreachable.

- Code: `agents/hephaestus/agent_executor.py`
  (`_delegate_chat_to_agent`).
- Unit tests: `tests/unit/test_hephaestus_chat_delegation.py`
  (5 cases — happy path, URL targeting, unreachable, mid-stream
  error, INPUT_REQUIRED).
- Live smoke gated: needs AJ at keyboard to send `@aidos check this
  for jargon: <slop sample>`, `@puck`, `@cupid`, `@aletheia`
  end-to-end through the CLI + GUI and confirm the companion's
  container is actually invoked (visible in `docker logs aidos`).
