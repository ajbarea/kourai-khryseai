# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **Round 6 bullet 3** (CLI greeting
maiden-name attribution — third of the five M6-future bullets AJ
flagged from live smoke)

---

## Plan-of-record

End state: the random startup greeting line in the CLI tells the
player who is speaking. Pre-fix it rendered just `( ◡‿◡)✧ Structure IS
beauty.` — kaomoji + italic line, no name. Players had to memorize
the emoji-to-name map to attribute the line; the gallery and the
agent READMEs already do that work, but the very first interaction
threw it away.

### Change — `_format_greeting` helper ✅ 2026-04-26

- [x] `hosts/cli/__main__.py`: new `_format_greeting(name, face,
      quote)` helper next to `_format_affinity_bar`. Capitalizes the
      maiden name, renders it in `_GOLD_BOLD`, then face in `_GOLD`,
      then quote wrapped in `"..."` and rendered `_ITALIC`. The
      `"..."` wrap is load-bearing: M10's speech-vs-action convention
      keys italic dialogue off a leading double-quote, so future
      readers maintain the styling without bespoke flags.
- [x] `_GOLD_BOLD` added to the styling import block.
- [x] Greeting call-site replaced — was a one-line f-string with face
      + quote; now an empty `_echo("")` followed by a call to the
      helper. The leading newline that used to live inside the
      f-string moved to its own `_echo("")` for legibility.

### Tests ✅ 2026-04-26

- [x] `tests/unit/test_cli.py::TestGreetingFormat`: 5 tests covering
      name-included, face-included, quote-wrapped-in-double-quotes,
      lowercase-input-capitalizes-output, and reading-order
      (name-precedes-face-precedes-quote with ANSI stripped). All
      pass in 0.6 s.

### Live smoke (folded into next interactive `/project` session)

- [ ] Launch CLI → confirm greeting line shows `<Name> <face>
      "<quote>"` and that the italic styling lands on the quoted
      text.
- [ ] Confirm name-color (`_GOLD_BOLD`) reads as a brighter accent
      than the rest of the line on AJ's terminal.

---

## Notes / open questions

- **Why title-case (`Metis`) over uppercase (`METIS`)?** The
  `_comms_window` callsign header uses `agent_name.upper()` because
  it's a status-bar-style label sitting inside a styled box, denser
  visual context. The greeting is the player's first-glance moment;
  title-case reads as a personal introduction, uppercase reads as a
  system label. Different surface, different convention.

- **Why wrap in `"..."` instead of just leaving the italic style
  flag?** Two reasons. (1) M10 already established that quoted text
  is dialogue everywhere — keeping the same convention here means the
  greeting line follows the same rule the rest of the CLI does. (2)
  If a future reader rewrites the greeting they'll see the `"..."`
  and infer the styling intent without reading any docs.

- **The remaining 2 Round 6 bullets are still open:**
  - WSL audio environment graceful handling (`SDL_AUDIODRIVER=dummy`
    when ALSA can't reach a card, gated on `/proc/sys/fs/binfmt_misc/WSLInterop`)
  - Git context discovery for specialist agents in worktree (containers
    default to `/app`, so `git status --short` exits 128 because the
    worktree is mounted elsewhere)
  Each is worth its own focused PR. Not bundled here so the diff stays
  scannable and the feature label on the PR is honest.

---

## Up next (queued, not yet active)

- **Other 2 Round 6 bullets** (WSL audio, git context discovery) —
  small focused PRs each.
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
