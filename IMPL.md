# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **`/project delete` confirmation guard**
(unscheduled — caught live in AJ's REPL session)

---

## Plan-of-record

End state: `/project delete <name>` no longer nukes a project on a
single keystroke. Two-tier confirmation matches what
`_reset_progression_data` already does for the destructive-settings
path:

- **bare delete** (registry-only; project files survive at the path) →
  `[y/N]` prompt, default-no.
- **`--purge`** (`shutil.rmtree` on the project dir; irreversible) →
  typed-name confirmation `Type DELETE <name> to confirm`.
- **`--yes` / `-y`** flag bypasses both for headless / scripted use.

### Step 1 — Two-tier confirmation helper ✅ 2026-04-26

- [x] `hosts/cli/commands.py::_confirm_project_delete` — single
      function with a `purge` kw-only flag; the docstring spells out
      why the two tiers exist (different blast radius). Modeled on
      the existing `_reset_progression_data` typed-name pattern so
      the convention stays uniform across destructive commands.

### Step 2 — Wire into the `delete` branch ✅ 2026-04-26

- [x] `hosts/cli/commands.py` `delete` branch:
      - Parse `--yes` / `-y` alongside the existing `--purge`.
      - Call `_confirm_project_delete(...)` unless `skip_confirm`.
      - On cancel, print `Cancelled. No data changed.` and bail out
        (matching `_reset_progression_data`'s phrasing).
      - On success, the message now distinguishes the two paths:
        purge says `purged <path>`; bare says `Files survive at
        <path> — re-add with /project new <name> against that path
        to restore.`
- [x] `hosts/cli/completer.py`: arg-hint updated to
      `<name|id> [--purge] [--yes]` and description grew the
      `(asks to confirm)` qualifier so the slash menu surfaces the
      new behaviour.

### Step 3 — Tests ✅ 2026-04-26

- [x] `tests/unit/test_project_delete_confirm.py`: 16 tests across
      4 classes:
      - `TestBareDeleteAsksYesNo` (6) — y/yes/Y proceed; n / empty /
        garbage cancel.
      - `TestPurgeRequiresTypedName` (5) — typed name proceeds;
        `y` alone, wrong name, `DELETE` alone, lowercase variant
        all cancel.
      - `TestYesFlagBypassesConfirm` (3) — `--yes` and `-y` bypass
        both bare and purge prompts (asserted by raising on
        `input()`).
      - `TestActiveProjectClearedOnDelete` (2) — `settings.save()`
        only fires when delete actually proceeds.
      - Whole file passes in 0.31 s.
- [x] Full unit suite: **2493 passed in 62 s** on parallel workers
      (was 2477 + 16 new — no regressions).

### Step 4 — Live smoke (queued for next interactive session)

- [ ] `/project delete hello-forge` → confirm `[y/N]` prompt,
      `n`/Enter cancels with `Cancelled. No data changed.`, `y`
      proceeds with the new "files survive at …" message.
- [ ] `/project delete hello-forge --purge` → confirm typed-name
      prompt; typing the wrong name cancels; typing `DELETE
      hello-forge` proceeds and prints `purged <path>`.
- [ ] Headless: `python -m hosts.cli -p '/project delete hello-forge --yes'`
      → confirm bypass works for non-interactive runs.

---

## Notes / open questions

- **Why default-no on bare `[y/N]`?** Per the destructive-default
  convention — Enter on a confirmation prompt without any keystroke
  must NOT proceed. Same as `git clean -i` and most coreutils.

- **Why typed-name (not just `[y/N]`) for `--purge`?** Because
  tab-completion + Enter on a slash popup can hand the user a
  pre-filled `/project delete hello-forge --purge`, and a single
  reflexive `y` would `rm -rf` the project. The typed-name guard
  forces the user to actually look at and acknowledge the project
  name before the destructive action runs. Same logic
  `_reset_progression_data` uses for "Type RESET to confirm".

- **`--yes` is a single-flag escape hatch.** Headless / scripted
  uses (CI cleanup tasks, tutorial-reset scripts) need a way to skip
  the prompt without faking stdin. The flag is documented in the
  slash-menu hint so anyone who notices it knows what it does.

---

## Up next (queued, not yet active)

- **AJ's `_clear_screen` WIP** in `hosts/cli/__main__.py` +
  `hosts/cli/rendering.py` — bypasses prompt_toolkit's ESC
  sanitization so `/clear` actually works. Hand off when AJ wants
  it folded into a PR.
- **M2** (`kourai-forge-mcp` server) — gated on M1 Round 6 smoke.
- **M9** (Opus 4.6 → 4.7 in `MODELS_SMART["metis"]`) — one-line
  bump, also wants Round 6 smoke.
- **M5** (UID alignment for forge worktrees) — quality-of-life,
  needs live docker testing.
- **M7** (a2a-sdk 1.0.x migration) — properly scoped, needs live
  A2A smoke.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor
  on the board.
- **Companion / spirit READMEs** (Puck, Cupid, Aidos, Aletheia) —
  when M6 work crystallises.
