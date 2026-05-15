# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

Updated: 2026-05-15

## In flight

Nothing actively building. Recent sweep on 2026-05-15 cleared two IMPL
entries: M14 parallel timeout shipped (#c46ce56 tuned aiohttp pool +
streaming timeout; #0d86fed unit tests; #f1481b8 diagnostics) and the
host-area docstring deslop pass landed (#190). CI fast lane was also
restored (#188) so the pre-push gate gates again.

## Next pickups

Working through these in order — small, self-contained, don't need AJ at the keyboard:

- **Cross-host status-feed** — `kourai_common.status_feed` (RingBuffer[T]
  + StatusEvent typed record). Replaces `hosts/gui/debug_log.py` + the
  deleted status_bubbles parallel state stores. Two current writers (CLI
  `/debug` slash, file-write). GUI bottom-overlay subscriber is anticipatory;
  skip it.
- **Puck Slice 2 helper** — `_invoke_agent_live(agent, prompt, fallback,
  timeout)` A2A timeout-and-fallback wrapper. Skip the `/replay-tutorial`
  command pending Slice 3 (replays a still-stub flight scene = anticipatory).

After that: **M6 ElevenLabs hybrid** is the next milestone (gated on
M20 + VN smoke landing first; full spec in
[ROADMAP.md → M6](./ROADMAP.md#m6--elevenlabs-hybrid-pre-player-release-blocker)).
