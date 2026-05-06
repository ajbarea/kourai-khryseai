# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

Updated: 2026-05-06

## In flight

Nothing actively building. NE Agents Day prep shipped through #184; the
QR-code reviewer experience is verified end-to-end. Friday's poster
session is a passive watch.

## Next pickups

After Friday, working through these in order — small, self-contained,
don't need AJ at the keyboard:

- **Hephaestus aiohttp `TimeoutError` on M14 parallel routing.** Smoke
  on 2026-05-06 sent `"hi dokimasia, are you there?"` to hephaestus;
  HTTP 200 SSE opened but body never streamed. Container logs show
  `_execute_completion failed (attempt 2), retrying in 4.4s:
  TimeoutError`. Network from inside the container reaches
  `api.anthropic.com` cleanly via `urllib`; hang is at the LiteLLM +
  aiohttp transport layer. Retry logic IS firing — system is resilient,
  just slow. File a GitHub issue with reproduction + log capture.
- **Karaoke Tier 2 fallback prints empty `""` quote pair when Kokoro on
  CPU doesn't fire `on_word` callbacks.** Cosmetic. Fix is to fall
  through to a static text print in the karaoke close path when no words
  were revealed.
- **`docs/configuration.md` accuracy + spirits tier-table decision.**
  README simplified tier table omits aidos/aletheia/cupid/puck rows;
  docs page should either fully list them or explicitly link to
  `shared/src/kourai_common/config.py` as canonical.
- **Host-area docstring deslop pass** that #184 deferred —
  Manages/Handles/Provides narrative WHAT-comments in `hosts/cli/` and
  `hosts/gui/`.

After those: **M6 ElevenLabs hybrid** is the next milestone (gated on
M20 + VN smoke landing first; full spec in
[ROADMAP.md → M6](./ROADMAP.md#m6--elevenlabs-hybrid-pre-player-release-blocker)).
