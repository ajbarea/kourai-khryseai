# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **Round 6 bug cleanup** (two
M6-future bullets AJ noted from live smoke)

---

## Plan-of-record

End state: two concrete bugs from Round 6 are gone. Both surfaced
when AJ ran live smoke, both bit the player experience, both have
small-surface fixes:

1. **`read_file` accepts directory paths** → returns garbage. Tighten
   the schema description so the LLM gets the hint at request time;
   add a runtime `is_file()` guard so when the model still tries it,
   the error is actionable instead of silent.
2. **Branch slug logic only handled spaces** → backticks (and every
   other shell-meta) slipped through, producing
   `please-add-a-function-\`d` from a Round 6 prompt. Replace with
   a `[a-z0-9-]` whitelist so anything weird gets squashed; also
   collapse hyphen runs and strip edges.

### Change 1 — read_file rejects directories ✅ 2026-04-26

- [x] `shared/src/kourai_common/forge_tools.py::read_file` schema:
      function description and `path` param description both call
      out "regular file path, not a directory". Example added in
      the param description.
- [x] `read_file` handler: `target.is_dir()` check returns a clear
      error string ("X is a directory; read_file expects a regular
      file. Use a more specific path or list the directory contents
      yourself before calling read_file."). Doesn't crash, doesn't
      return garbage — gives the LLM a clear next step.

### Change 2 — branch slug sanitization ✅ 2026-04-26

- [x] `shared/src/kourai_common/forge_session.py`: new
      `_sanitize_branch_slug(label, max_len=24)` helper.
      Conservative whitelist `[a-z0-9-]` over enumerating
      `git check-ref-format`'s blocklist — handles every
      shell-meta and quote character at once. Collapses runs of
      hyphens, strips leading/trailing, truncates to `max_len` then
      strips any trailing hyphen the truncation produced.
      Empty/None → `"session"` so the branch always shapes
      `forge/<timestamp>-<slug>`.
- [x] `ForgeSession.start` calls the helper instead of the old
      one-liner. No call-site changes.

### Tests ✅ 2026-04-26

- [x] `tests/unit/test_forge_tools.py::TestReadFile`:
      - `test_rejects_directory_path` — explicit guard test
      - `test_schema_description_warns_against_directory_paths` —
        contract test naming the schema requirement
- [x] `tests/unit/test_forge_session.py::TestSanitizeBranchSlug`:
      9 tests — simple lowercasing, backtick-replaced (the exact
      Round 6 case), quotes, hyphen-collapse, edge-stripping,
      empty fallback, truncation without trailing hyphen,
      lowercasing, property-style "every char is in [a-z0-9-]" check
      across weird/unicode/shell/path/escape inputs.
- [x] All 14 new tests pass in 0.43 s.

### Step 4 — Live smoke (folded into next interactive `/project` session)

- [ ] Send a prompt with a backtick (e.g. ``please add a function `d` ``)
      → confirm the forge branch shape is well-formed
      (`forge/20260426-…-please-add-a-function-d` with no backtick).
- [ ] Send a Techne task that touches a directory → confirm Techne
      gets the new clear error and routes around it (e.g., reads a
      specific file inside the directory) instead of failing silently.

---

## Notes / open questions

- **Whitelist over blocklist.** Git's `check-ref-format` blocks
  ASCII control chars, space, tilde, caret, colon, question mark,
  asterisk, open bracket, plus several path-rule violations. Enumerating
  is fragile (Git updates the rules) and forgets shell metacharacters
  that aren't strictly invalid but break elsewhere. `[a-z0-9-]` is
  conservative — accepts everything that's safe by inspection.

- **Why `is_file()` AND the schema hint?** The schema hint is the
  carrot — the LLM sees it during prompt construction and avoids the
  mistake. The runtime check is the stick — when it tries anyway,
  the error is actionable. Both layers cost ~5 lines and remove a
  whole class of confusion AJ saw in Round 6.

- **The other 3 Round 6 bullets are still open:**
  - CLI greeting maiden-name attribution
  - WSL audio environment graceful handling
  - Git context discovery for specialist agents in worktree
  Each is worth its own focused PR. Not bundled here so the diff
  stays scannable.

---

## Up next (queued, not yet active)

- **Other 3 Round 6 bullets** (greeting attribution, WSL audio, git
  context discovery) — small focused PRs each.
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
