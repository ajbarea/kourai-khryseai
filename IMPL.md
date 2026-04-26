# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **M10 — Speech-vs-action rendering convention**

---

## M10 plan-of-record

End state: every host (CLI, GUI, VN) treats a leading double-quote as the
single signal that decides "this line is dialogue, render it italic" vs
"this line is a status report, render it plain". Every agent's
SYSTEM_PROMPT carries the rule so the LLM emits the right shape; every
host renderer carries the matching detector so the player sees the
distinction. The maidens stop reading like CLI tools.

### Step 1 — `UNIVERSAL_RULES` carries the convention ✅ 2026-04-26

- [x] `shared/src/kourai_common/prompts.py`: added a 9th rule to
      `UNIVERSAL_RULES` ("SPEECH VS ACTION") covering quoting and what
      the host does with it. `build_system_prompt()` already appends
      `UNIVERSAL_RULES` to every specialist, so all 9 specialists
      (Metis, Techne, Kallos, Dokimasia, Mneme, Puck, Cupid, Aidos,
      Aletheia) inherit the rule with zero per-agent edits.

### Step 2 — Hephaestus's hand-rolled prompt + handoffs ✅ 2026-04-26

- [x] `agents/hephaestus/agent.py`: `ROUTING_PROMPT` got the same
      `SPEECH VS ACTION` paragraph plus quoted forms of the `CHAT:` and
      `ASK_USER:` examples (the routing tokens stay unquoted — protocol,
      not speech).
- [x] Every value in `HEPH_HANDOFFS` (15 lines across 5 keys) wrapped
      in double quotes — the ROADMAP table lists "handoff line" under
      Talking. Default fallback in `get_heph_narration()` quoted too.
- [x] Inline narration in `execute_pipeline` (`loop_msg`, `check_msg`,
      the iteration-cap message) wrapped — same reason.

### Step 3 — CLI italic on quoted lines ✅ 2026-04-26

- [x] `hosts/cli/rendering.py::_comms_window`: detects leading `"`
      after `lstrip()`, applies `_ITALIC` for the dialogue text. The
      `whisper` style composes `_DIM + _ITALIC` for outgoing-maiden
      handoff parting shots so they read as both dialogue *and* fading.
      Status lines stay plain. `_maidenify_status` doesn't need a touch
      — it routes through `_comms_window`.

### Step 4 — GUI italic on quoted lines ✅ 2026-04-26

- [x] `hosts/gui/dialogue.py`: new `_is_quoted_dialogue` helper +
      `oblique` keyword on `_draw_line_with_emotes`. When the entry
      text starts with `"` the body renders with
      `pygame.freetype.STYLE_OBLIQUE` (synthesised italic — no font
      asset add). `*emote*` spans keep their dim-gold treatment
      regardless. The GUI matches the CLI line-for-line.

### Step 5 — VN: scrub orphan `what_prefix` ✅ 2026-04-26

- [x] `hosts/vn/kourai_vn/game/script_data.rpy` (8 main agents) was
      already Hades-style as of an earlier pass.
- [x] `hosts/vn/kourai_vn/game/script_labels.rpy:67-68` (aidos and
      aletheia debug-only Character defs) had the legacy
      `what_prefix='"', what_suffix='"'` — stripped, with the same
      explanatory comment as `script_data.rpy`. `grep -rn what_prefix
      hosts/vn/` returns zero hits.

### Step 6 — Tests ✅ 2026-04-26

- [x] `tests/unit/test_speech_vs_action.py`: 26 tests across 6 classes:
      `TestUniversalRule` (2 + 5 parametrised), `TestHephaestusRoutingPrompt`
      (3), `TestHephaestusHandoffs` (4), `TestCommsWindowItalic` (4),
      `TestGuiIsQuotedDialogue` (6 parametrised + 1 signature guard),
      `TestVnNoBlanketQuoting` (1 walks every `*.rpy` for `what_prefix`).
      Whole file passes in 2.93 s.

### Step 7 — Docs refresh

- [ ] Sample CLI transcript in README.md / docs/cli.md updated where it
      contradicts the new convention. Only touch lines that are now
      *wrong* — don't fabricate prose to demonstrate the change.

### Step 8 — Live smoke (queued for next interactive `/project` session)

The visual outcome (italic agent dialogue, plain status) needs eyes on
the running CLI/GUI to confirm. Adding to the existing
[SMOKE_TODO.md](./SMOKE_TODO.md) follow-up list:

- [ ] CLI: send "@metis plan a CSV exporter" → confirm Metis's
      clarifying question renders italic, the subsequent
      file-listing/pytest lines stay plain.
- [ ] GUI: same task → confirm dialogue bubbles render with
      synthesised italic, status bubbles stay upright.
- [ ] VN: scripted demo → confirm name plaque carries identity, no
      double-quote chrome around lines that are *not* themselves quoted
      by the agent.

---

## Notes / open questions

- **Italic in terminals.** `_ITALIC = "\033[3m"` works in every modern
  emulator (WSL, iTerm, Terminal.app, Windows Terminal, VSCode,
  WezTerm, Hyper, Kitty, Alacritty). A handful of legacy terminals
  swallow SGR 3 silently; the rendered text just stays upright on
  those. No fallback needed — italic is decoration, not information.

- **Pygame oblique vs true italic.** `STYLE_OBLIQUE` synthesises italic
  by skewing the regular face. It's slightly less elegant than a real
  italic font file but ships zero new assets and looks correct at every
  zoom level the GUI supports today. If/when M12 (dynamic sizing) lands
  and the font system grows a registry, dropping in an italic asset and
  swapping `STYLE_OBLIQUE` → real italic is a one-line change.

- **Why quote, not bracket?** `"..."` is what fiction uses. The maidens
  are characters, not CLI tools — the convention is borrowed from the
  300-year-old prose convention, not invented for this product. It also
  keeps the model's output grep-friendly: `grep '^"' transcript.txt`
  filters dialogue out of a session log.

---

## Up next (queued, not yet active)

- **M2** (`kourai-forge-mcp` server) — gated on M1 Round 6 smoke
  ("we've felt whether the toolset is right" — needs the live CLI
  loop, not unit tests).
- **M3** (A2A streaming task events) — biggest UX win still on the
  board; the speech-vs-action work makes per-stage updates *legible*,
  M3 makes them *real-time*.
- **M9** (Opus 4.6 → 4.7 in `MODELS_SMART["metis"]`) — one-line bump,
  safe to slip in alongside any future PR that touches `config.py`.
