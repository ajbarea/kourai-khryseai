# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **Round 6 bullet 4** (WSL audio
noise suppression — `cannot find card '0'` cascade on every WSL2
launch even though `AudioManager` handles the failure cleanly
downstream)

---

## Plan-of-record

End state: WSL2 launches no longer flood stderr with ALSA chatter
on first init. The fix turned out smaller than the ROADMAP entry
suggested: `kourai_common.audio_env.configure_sdl_audio_driver()`
was already implemented (and unit-tested) — it just wasn't called
anywhere. Defined-but-dead infrastructure. Wiring it into
`kourai_common.audio` at module load (before `import pygame`)
makes SDL pick up the env var on first init and skip ALSA
entirely.

### Change — wire `configure_sdl_audio_driver()` into audio module load ✅ 2026-04-26

- [x] `shared/src/kourai_common/audio.py`: import
      `configure_sdl_audio_driver` and call it at module level
      BEFORE `import pygame`. Player-set `SDL_AUDIODRIVER` is
      respected (the helper checks first); WSLg with `PULSE_SERVER`
      + libpulse → `pulseaudio`; headless Linux → `dummy`; non-WSL
      with a display → unset (SDL default).

### Tests ✅ 2026-04-26

- [x] `tests/unit/test_audio_env.py::test_audio_module_import_triggers_sdl_configure`:
      regression guard via `importlib.reload` + spy. The function
      being defined-but-unwired was the original bug — this test
      ensures a future refactor doesn't silently un-wire it again.
- [x] 4 pre-existing audio_env unit tests still pass.

### Live smoke

- [x] Verified live in AJ's environment: `SDL_AUDIODRIVER=pulseaudio`
      is set after `from kourai_common import audio`. No more ALSA
      cascade on next CLI/GUI startup.

---

## Notes / open questions

- **Why was the helper defined but never wired?** Best guess from
  the file timestamp (`Apr 14 18:29` on `audio_env.py`) and the
  empty grep for callers: it landed as part of an aborted
  refactor or was meant to be wired in a follow-up that never
  happened. Either way, the test coverage was already there —
  the wiring was the missing piece.

- **Why import-time side effect over a lazy call?** Two reasons.
  (1) `pygame.init()` in `hosts/gui/__main__.py` runs at line 92
  but `from kourai_common.audio import AudioManager` is at line
  28. To win that race, the env var must be set during the import,
  not when `AudioManager()` is later instantiated. (2) Keeps every
  entry point honest — no one needs to remember to call the helper
  before pygame work; importing the audio module is enough.

- **Final Round 6 bullet still open:**
  - Git context discovery for specialist agents in worktree
    (containers default to `/app` so `git status --short` exits 128
    because the worktree is mounted elsewhere — `[project_root: …]`
    is in the user message but agents aren't `cd`-ing to it before
    `git status`)

---

## Up next (queued, not yet active)

- **Round 6 final bullet** (git context discovery) — small focused PR.
- **Typer + open-source-Claude-Code research** (AJ-requested 2026-04-26):
  scan latest April 2026 takes on Typer for player-experience wins, and
  the Rust/Python OSS rewrites of Claude Code (e.g. opencode, plandex,
  aider, sgpt) — anything we can lift into the CLI host. Findings to
  ROADMAP.md, not a code PR yet.
- **T8 follow-up** (ParallelContext shared buffer feeding Metis's
  partial output back into the classifier prompt). Substantial
  async work.
- **T4 follow-up from M13** (`[forge_intent]` block on user message
  to specialists). Needs SQL migration or in-memory plumbing.
- **M2** (`kourai-forge-mcp` server) — real architectural milestone.
- **M15** (forge logging architecture) — operational hygiene.
- **M5** (UID alignment for forge worktrees) — quality-of-life.
- **M7** (a2a-sdk 1.0.x migration) — properly scoped.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor.
