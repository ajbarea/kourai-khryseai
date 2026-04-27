# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **`A2A-Version` header + `/cost`
alias** (tier-4 + tier-5 lifts from the OSS-CC research sweep, bundled
because both are small and independent — single PR keeps the cadence
moving without a 5-line standalone)

---

## Plan-of-record

End state: every outbound A2A request carries the spec-required
`A2A-Version` header (so a future a2a-sdk 1.0.x server doesn't
silently downgrade the negotiation to 0.3 semantics), and players
arriving with muscle-memory from ClawCode / Cline / OpenCode can
type `/cost` instead of having to relearn `/usage`.

Both pieces are tiny on their own. Bundling preserves
one-PR-per-shippable-tier cadence without making the WSL-audio /
greeting-attribution PRs look big by comparison.

### Change 1 — `make_a2a_http_client` helper + 4 wiring sites ✅ 2026-04-26

- [x] `shared/src/kourai_common/a2a_utils.py`: new
      `A2A_PROTOCOL_VERSION = "0.3"` constant + `make_a2a_http_client(*,
      timeout=None, extra_headers=None) -> httpx.AsyncClient` factory
      that sets `A2A-Version` on every constructed client. `extra_headers`
      merges with the version header for callers that need additional
      defaults; an explicit `A2A-Version` in `extra_headers` wins
      (defensive — lets a compat-test override the value).
- [x] `agents/hephaestus/remote_connections.py`: replaced the inline
      `httpx.AsyncClient(timeout=httpx.Timeout(...))` with
      `make_a2a_http_client(timeout=...)`.
- [x] `hosts/cli/__main__.py`, `hosts/cli/headless.py`,
      `agents/vn_bridge.py`: same swap. `vn_bridge.py` `httpx` import
      moved into the `TYPE_CHECKING` block since it's now only
      referenced as a forward-ref string in `cast`.

### Change 2 — `/cost` alias for `/usage` ✅ 2026-04-26

- [x] `hosts/cli/__main__.py`: REPL dispatch now matches
      `if prompt_text in ("/usage", "/cost"):` so both route to
      `_show_usage_summary`.
- [x] `hosts/cli/completer.py`: new `SlashCommand("cost", "Alias for
      /usage — matches OSS-CC vocabulary (ClawCode, Cline, OpenCode)")`
      so the popup and `/help` surface it.

### Tests ✅ 2026-04-26

- [x] `tests/unit/test_a2a_utils.py::TestA2AHttpClient` — 5 tests:
      default carries `A2A-Version`, version-pin regression guard
      (`A2A_PROTOCOL_VERSION == "0.3"` so the eventual M7 bump is
      deliberate), `extra_headers` merge without overriding the
      version, `timeout` passes through to `httpx.AsyncClient`,
      explicit override of the version in `extra_headers` wins.
- [x] `tests/unit/test_usage.py::TestUsageSlashCommand` — 3 new
      tests: `/cost` registered in `SLASH_COMMANDS`, REPL dispatch
      resolves to the same handler as `/usage` (source-level
      assertion via `inspect.getsource` so a future refactor that
      splits the branches gets caught), pre-existing
      `_show_usage_summary` tests still green.
- [x] All 116 tests across `test_a2a_utils.py`, `test_usage.py`,
      `test_cli.py`, `test_confirmation_protocol.py` green.

### Live smoke (folds into next interactive `/project` session)

- [ ] Send a Hephaestus request, then check container logs (or
      enable httpx debug) → confirm `A2A-Version: 0.3` is present on
      every outbound request.
- [ ] Type `/cost` in the REPL → confirm the same usage summary
      `/usage` produces.

---

## Notes / open questions

- **Why "0.3" and not "1.0" as the declared version?** The spec
  says the client MUST send the version it speaks; if it lies,
  the server treats every request as 1.0 semantics and our 0.3
  client breaks. We declare the truth — 0.3 — so a 1.0-aware
  server can treat us with backward compatibility. When M7 lands
  and we move every Part construction to the unified-Part shape
  (see ROADMAP M7 spec deltas section), the constant flips to "1.0"
  in lockstep with the SDK pin. The version-pin regression test is
  there so that bump is deliberate.

- **Why centralise into `make_a2a_http_client` rather than just
  add the header at each construction site?** Four current sites,
  with M2 (kourai-forge-mcp) likely to add a fifth and the
  voice-lab spinoff likely to add a sixth. Already past the "rule
  of three" for extracting a helper; doing it now is cheaper than
  adding the header six times in four months.

- **Why bundle these two unrelated lifts?** Each is too small for
  its own PR (one helper + 4 swap-sites; one alias entry + 1
  dispatch tuple). Splitting them would make each look like
  busy-work and clutter the PR list. They share the
  "tier-4 + tier-5 OSS-CC follow-up" theme. If a future bisect
  ever needs to roll one back independently, the commit history
  is clean enough to revert just the `/cost` lines.

- **What this lift does NOT do.** It does not flip the SDK pin to
  ≥1.0 — that's M7. The header is a prerequisite for M7, not the
  whole migration. Pyproject pins still cap at `<1.0` until M7 is
  ready (see M7 section in ROADMAP for the full spec-delta scope).

---

## Up next (queued, not yet active — tier order from #37 prioritization, all tier-1-through-5 now done)

- **MCP `roots` + `elicitation` declared at M2 init** — design-time
  work for when M2 (`kourai-forge-mcp`) is being scaffolded. The
  prerequisite chain to M2 itself (M1 done) is complete; pulling
  M2 into the active queue is a real possibility.
- **Plan Mode toggle (Cline-style)** — persistent planning mode
  where Hephaestus loops on M14 parallel routing every turn but
  never dispatches until the player explicitly types `/plan
  execute`. Bigger lift than the tier-1-5 follow-ons, but next-
  tier shippable.
- **Background memory consolidation (Mneme "autoDream")** —
  ClawCode pattern; pairs nicely with the just-shipped `/compact`.
- **Custom-agent-via-markdown registration (OpenCode-style)** —
  long-term direction; touches A2A registration, MCP toolkit, and
  routing prompt, so wait until M2 lands.
- **Tree-sitter project mapping (Plandex-style)** — pre-computed
  PROJECT_MAP block in prompts; pairs with M4 caching.
- **LSP integration for forge tools (OpenCode-style)** — biggest
  architectural pickup; new `lsp_diagnostics` and `lsp_rename`
  forge tools.
- **T8 follow-up** (ParallelContext shared buffer feeding Metis's
  partial output back into the classifier prompt). Substantial
  async work.
- **T4 follow-up from M13** (`[forge_intent]` block on user message
  to specialists). Needs SQL migration or in-memory plumbing.
- **M2** (`kourai-forge-mcp` server) — real architectural milestone.
- **M15** (forge logging architecture) — operational hygiene.
- **M5** (UID alignment for forge worktrees) — quality-of-life.
- **M7** (a2a-sdk 1.0.x migration) — properly scoped; the
  `A2A-Version` header is now in place as a prerequisite.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor.
