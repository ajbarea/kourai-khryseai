# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-27 · Working on: **Spec drift watcher cron** —
turning "track latest aggressively" from an ad-hoc nudge-driven habit
into a triageable inbox item.

---

## Plan-of-record

End state: every Sunday at 13:00 UTC, a small GitHub Actions job
fetches a hand-curated list of MCP + A2A spec/SDK URLs, computes a
per-source digest (HTML hash for spec pages, Atom-feed entry-title
hash for release feeds, version string for PyPI JSON), and compares
against the prior snapshot held in `actions/cache`. If anything
drifted, it opens a GitHub issue tagged `protocol-watch` summarising
the delta — title, prior/current digest, content excerpt, the watch's
own one-liner note, and a triage path that explicitly mentions M2 +
M7 as the likely owners.

The trigger is the spec moving instead of AJ remembering to nudge.
The 2026-04-27 finding that A2A v1.0's `Message.metadata` channel had
landed months before we noticed (and built around it with the
text-tag carrier) is the canonical "this is why we built the watcher"
story.

### Change 1 — `scripts/watch_protocols.py` ✅ 2026-04-27

- [x] `WATCHES` tuple: 7 sources today
  (`mcp-spec-2025-11-25`, `mcp-blog`, `a2a-spec-latest`,
  `a2a-releases`, `mcp-spec-releases`, `a2a-sdk-pypi`, `mcp-pypi`).
  Adding a new source is one append + a `Watch(...)` literal.
- [x] Three `_digest_*` functions matched to source kind so the diff
  signal stays meaningful — full HTML hash for spec pages, Atom feed
  entry-title hash for release feeds (so a feed metadata refresh
  doesn't trigger), version-string keying for PyPI (so the "drift"
  is literally "a2a-sdk: 0.3.26 -> 1.0.2").
- [x] `diff_watches(watches, state, fetcher)` is the pure core —
  pure function, fully unit-testable with a mock fetcher and an
  in-memory state dict.
- [x] Transient HTTP failures carry the prior baseline forward
  unchanged; a bad week doesn't wipe state. Unseen-watch fetch
  failure skips silently rather than recording a placeholder.
- [x] `--dry-run` (or `KOURAI_PROTOCOL_WATCH_DRY_RUN=1`) prints the
  would-be issue body to stdout instead of calling `gh`. Same flag
  is wired into the workflow's `workflow_dispatch` input.
- [x] Atomic state save via `state.json.tmp` -> `replace(state.json)`
  so a partial-write doesn't corrupt the snapshot.

### Change 2 — `.github/workflows/spec-watch.yml` ✅ 2026-04-27

- [x] Sunday 13:00 UTC cron + `workflow_dispatch` for manual runs
  (with a `dry_run` input that maps to the env var).
- [x] State persistence via `actions/cache` keyed on
  `spec-watch-state-${run_id}` with `restore-keys: spec-watch-state-`
  prefix — `actions/cache/save@v4` always runs (`if: always()`) so
  partial fetch failures still save the carried-forward state.
- [x] Minimal install (`pip install httpx`) — full `uv sync` would
  burn ~2 minutes for a script that just needs httpx.
- [x] `permissions: issues: write` so `gh issue create` works with
  the default `GITHUB_TOKEN`. No extra secrets needed.

### Change 3 — Tests ✅ 2026-04-27

- [x] `tests/unit/test_watch_protocols.py` — 29 tests covering:
  - `TestDigesters` (9): per-kind digest stability, sensitivity to
    real changes, malformed-JSON handling, excerpt content.
  - `TestDiffWatches` (5): empty-state initial run emits no issues
    (the "we just started watching" case), unchanged run no-op,
    changed run fires per-watch, transient HTTP error preserves
    prior state, unseen-watch fetch failure skips silently.
  - `TestFormatIssueBody` (1): canonical fields present so future
    readers can grep for them.
  - `TestStateRoundtrip` (5): missing/malformed state file returns
    empty dict; save+load roundtrips; parent-dir auto-create;
    atomic .tmp pattern leaves no leftovers.
  - `TestOpenIssueDryRun` (2): dry-run path never invokes
    subprocess; missing-repo also falls through to dry-run.
  - `TestWatchesContract` (4): unique keys, every kind has a
    digester, every URL is https, every watch has a non-empty note.
  - `test_digester_returns_str_str` (3 parametrized): defensive
    contract that all digesters return `(str, str)`.

### Live verification ✅ 2026-04-27

- [x] Dry-run against live URLs: all 7 fetched 200 (one had a 301
  redirect — caught + canonical URL substituted).
- [x] Synthetic-drift dry-run: stale-seeded state correctly produced
  the expected `Protocol watch: a2a-sdk-pypi drifted (0.3.26 -> 1.0.2)`
  issue body with the right title format and triage block.
- [x] PyPI snapshot capture confirms current versions: a2a-sdk 1.0.2
  (we're pinned `<1.0`), mcp 1.27.0 (active in our memory-mcp
  + context7-mcp containers).

### Initial CI run

After the PR merges, the **first** workflow run will see no prior
cache and treat everything as initial — the cache file gets seeded
with current digests and zero issues open. The **second** run
(Sunday) is the first real diff opportunity. To smoke-test sooner,
trigger via `workflow_dispatch` with `dry_run=true` and inspect the
log output.

---

## Notes / open questions

- **Why state in actions/cache rather than committed?** Two reasons.
  (1) Committing snapshot updates would require a `git push` step
  with branch-protection bypass — fragile and noisy. (2) Cache loss
  is benign — the next run treats it as initial and emits zero
  issues, and we lose at most one diff cycle. The trade is "no
  permanent record of every check" for "no commit-spam." Accepted.

- **Why a hardcoded `WATCHES` list instead of a YAML config?** Today
  there are 7 entries and adding one is a 5-line dataclass literal.
  YAML config would be more orchestrator-friendly but adds a parse
  step + schema discipline for a list that grows by maybe one entry
  per quarter. Move to config when we hit ~20 watches or want
  per-environment overrides.

- **Why not also watch docker images** (jaegertracing/all-in-one,
  prom/prometheus, etc.)? Lower priority — those are infrastructure
  pinned in compose, not protocol-defining. Adding them is a future
  one-line `Watch(... kind="docker-tag" ...)` once we write that
  digester. Skip for v1.

- **Why no `gh` smoke-test in CI?** The actual `gh issue create`
  call only runs in the live workflow with `GH_TOKEN` set; locally
  it falls back to dry-run. Mocking `subprocess.run` covers the
  command-construction path, and we'd be testing GitHub's API
  rather than our code. Live failure surfaces in a noisy log and
  the state file still persists, so the next run isn't blocked.

---

## Up next (queued, not yet active)

- **MCP `roots` + `elicitation` declared at M2 init** — design-time
  work for when M2 (`kourai-forge-mcp`) is being scaffolded.
- **M2** (`kourai-forge-mcp` server) — real architectural milestone;
  unblocked since M1 done. The watcher will start flagging MCP spec
  changes that affect M2's roots/elicitation/sampling implementation.
- **Plan Mode toggle (Cline-style)** — persistent planning mode.
- **Background memory consolidation (Mneme "autoDream")** — pairs
  with the just-shipped `/compact`.
- **Custom-agent-via-markdown registration (OpenCode-style)** —
  long-term direction; wait until M2 lands.
- **T8 follow-up** (ParallelContext shared buffer feeding Metis's
  partial output back into the classifier prompt).
- **T4 follow-up from M13** (`[forge_intent]` block on user message
  to specialists).
- **M15** (forge logging architecture) — operational hygiene.
- **M5** (UID alignment for forge worktrees) — would let us drop
  the `safe.directory '*'` workaround from #42.
- **M7** (a2a-sdk 1.0.x migration) — the watcher's a2a-sdk-pypi
  entry will fire when 1.0.x stabilises and we should flip the
  pin. The Message.metadata migration item is queued under M7's
  scope as a follow-on once the SDK pin flips.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor.
