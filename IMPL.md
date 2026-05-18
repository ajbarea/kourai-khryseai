# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever's in flight **right now** — current PR,
open design question blocking me, immediate next pickup. Queued specs,
cross-cutting invariants, and "next up" ordering live in
[ROADMAP.md](./ROADMAP.md). Git history is the archive.

If this file is more than ~50 lines, something queued or referential has
crept in — extract it back to ROADMAP.

Updated: 2026-05-18

## In flight

Five PRs open as of 2026-05-18, in roughly this merge order:

1. **#197 `feat/voice-examples`** — CLEAN, independent, ready to merge.
2. **#196 `feat/theoros`** — CLEAN after the test-isolation fix
   (commit 77e2b58 — autouse `_isolated_skill_context` fixture for
   `test_theoros_script.py`). Retarget #198 to main before merging
   this one (stacked-base rule).
3. **#199 `docs/generalize-poster-title`** — CHAI 2026 poster title
   generalized to "Multi-Agent Software Development"; docs-only.
4. **#198 `feat/theoros-autopilot`** — autopilot mode for theoros;
   stacks on #196. Rebased onto fixed feat/theoros HEAD; needs
   retarget-to-main once #196 lands.
5. **#200 `fix/dev-cli-demo-targets`** — registers cli-demo /
   gui-demo / vn-demo in `dev_cli.TASK_GROUPS` so `make help`
   surfaces them. Adds `Task.env_extra` to wire `KOURAI_POSTER_DEMO`
   for vn-demo without a Makefile env-prefix hack. Surfaced
   2026-05-18 by auditing make-help vs Makefile reality.

The 2026-05-16 → 2026-05-17 freshness sweeps (#192/#193 model+pricing,
#194 infra, #195 app-SDK) shipped. The one deferred bump —
**RealtimeTTS 0.6.1 → 0.7.1** (KokoroEngine → KokoroVoice breaking
change) — is captured in ROADMAP under "Surfaced 2026-05-17 from
app-SDK freshness sweep" and gates on AJ-in-loop live smoke.

### Follow-up surfaced 2026-05-18

Three other Makefile targets bypass the delegation contract:
`smoke-m18` (uses `uvx --with pexpect`), `logs` / `logs-tail` (tail
helpers), `sandbox-image` (docker build). The tail helpers are
trivial enough to stay shell-only; `smoke-m18` and `sandbox-image`
are honest candidates for `TASK_GROUPS` registration once a second
caller (Windows dev? CI?) shows the cross-platform pain. Flagged
not filed.

## Next pickups

Re-audited 2026-05-16 against actual call sites. Previously-listed
"small self-contained" picks turned out to be anticipatory:

- ~~Cross-host status-feed~~ — no CLI `/debug` slash command exists
  (greps empty in `hosts/cli/`); sole consumer remains
  `hosts/gui/debug_log.py`. Skip until a real second consumer lands.
- ~~Puck Slice 2 helper~~ — `/replay-tutorial` is still stub-gated.
- ~~Cross-host gossip-render~~ — no host renderers yet; shared-logic-only.
- ~~Cross-host codex~~ — needs live VN smoke for the parchment-book
  renderer.

The clean current-caller picks are exhausted. Next moves require
either an intentional anticipatory-gate override (flag it in the PR
body) or **M20 + VN live smoke** to unblock M6 ElevenLabs hybrid.

**Audit-mode work always available**: docs/*.md drift sweep,
/techne:sisters cross-repo audit, CLAUDE.md / AGENTS.md drift check.

Next priority milestone: **M6 ElevenLabs hybrid** (full spec in
[ROADMAP.md → M6](./ROADMAP.md#m6--elevenlabs-hybrid-pre-player-release-blocker)).
