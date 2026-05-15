# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

Updated: 2026-05-14

## In flight

Nothing actively building. NE Agents Day 2026 poster session shipped 2026-05-10
(NYC, Jane Street). QR-code reviewer experience verified end-to-end;
demo fielded live. Back to full-speed development as of 2026-05-14.

## Next pickups

Working through these in order — small, self-contained, don't need AJ at the keyboard:

- **Hephaestus aiohttp `TimeoutError` on M14 parallel routing.** Smoke
  on 2026-05-06 sent `"hi dokimasia, are you there?"` to hephaestus;
  HTTP 200 SSE opened but body never streamed. Container logs show
  `_execute_completion failed (attempt 2), retrying in 4.4s:
  TimeoutError`. Network from inside the container reaches
  `api.anthropic.com` cleanly via `urllib`; hang is at the LiteLLM +
  aiohttp transport layer. Retry logic IS firing — system is resilient,
  just slow. File a GitHub issue with reproduction + log capture.

After that: **M6 ElevenLabs hybrid** is the next milestone (gated on
M20 + VN smoke landing first; full spec in
[ROADMAP.md → M6](./ROADMAP.md#m6--elevenlabs-hybrid-pre-player-release-blocker)).
