# Puck-Led First-Run Tutorial — Design Spec

> Status: spec'd 2026-04-24 · implementation queued · pairs with M6
> ElevenLabs hybrid (first-run voice quality is the load-bearing
> impression — better to land M6 prosody before tutorial wide-release)
>
> Scope: CLI host only (`hosts/cli/onboarding.py`). GUI and VN are
> explicit follow-ups.
>
> Cross-referenced 2026-05-05 against current May 2026 best practice
> for AI/CLI onboarding (progressive disclosure, in-fiction integration,
> ask-before-destructive). Spec's design moves still hold.

---

## Why this exists

Today's CLI onboarding (`hosts/cli/onboarding.py`) is a ~213-line scripted form: name, pronunciation, mode toggle, title, role, pronouns. Puck appears as two static italicized lines and Hephaestus as a single closing line. Neither agent is invoked. The form collects data; it doesn't *introduce* the player to the game.

This spec replaces the scripted form with a **flight-scene tutorial** in which Puck is invoked as an actual A2A agent and escorts the player to meet Hephaestus and the maidens for the first time. Vibe references: Berserk's Puck (chaotic-good trickster, comic relief, sweet underneath) + Yu Yu Hakusho ep. 1 (Botan ferrying Urameshi to King Enma — the psychopomp gas-up).

Three load-bearing UX moves:

1. **Mandatory onboarding for everyone** — even devs who "just want to code with the agents" go through the flight. Profile creation isn't optional.
2. **In-fiction mode gate** — instead of a radio button, the choice between gamified mode and focused mode is a *scene*: Hephaestus asks if Puck stays or gets banished "for what he did last time." Banishing Puck disables the gamey layer; keeping him keeps it.
3. **The tutorial *becomes* the session** — the player's idea pitch at the forge is captured as the first real session message and routed by Hephaestus to the appropriate maiden. No dead-drop between flavor and work.

---

## Section 1 — The flight scene

Beats are ordered. Lines marked **⚡** invoke the actual agent (Puck or Hephaestus) via A2A with a fallback to a canned line if the call fails or times out.

### 1. Cold open
Puck appears mid-recognition, no banner, no boxes:
> *"Oh. OH. You — you're the one who's been muttering about something you want built. Yeah, I heard you. Daimons hear things."*

(Narrative justification for Puck knowing about "the wild idea": he's a daimon, he overhears.)

### 2. The pitch + thinking-time gift
> *"Come on — we're going to the forge. I know someone who can help with that wild idea you mentioned. But think carefully about how you want to word it on the way — he's a pretty busy guy. You don't waste his time, you'll have his attention."*

This single beat does three jobs:
- Frames the destination (the forge) and the someone (no maidens revealed yet)
- Buys the player composition time during the rest of the flight
- Establishes Hephaestus's gruffness as *justified busyness*, which echoes through every later session

### 3. Liftoff
> *"Keep up. I'll explain on the way."*

### 4. Flight beat — name
> *"So. What do I tell him you go by?"*

Free text. Stored as `display_name` on the PlayerProfile.

### 5. Flight beat — pronunciation
> *"And how's it actually said? He'll mangle it otherwise — trust me."*

Free text, optional (Enter accepts the display name). Stored as `tts_name`.

### 6. ⚡ Flight beat — name riff
Live Puck LLM call, given the player's name, returns one short reaction line.

Fallback: *"Hmph. Works. He'll remember it."*

### 7. Flight beat — THE GAS-UP (maidens revealed here)
Three scripted Puck lines. This is the YuYu/Botan beat:

> *"Now listen. The big guy doesn't work alone. He forged his own — six of them, the kourai khryseai. Golden maidens. Each one handles a piece of the work: strategy, code, tests, style, memory. And him running the forge over all of it."*
>
> *"They're unbelievable. Genuinely. You'll see."*
>
> *"So when you're shaping your pitch — picture which one of them you need most. That'll tell you a lot about what to ask for."*

The third line gives the player a **thinking framework**: the maiden taxonomy (metis/techne/dokimasia/kallos/mneme + hephaestus running it) becomes the lens through which they shape their pitch. Combined with beat 2's "take your time" prod, this is a setup-payoff pair across the flight.

### 8. Flight beat — the callback seed
> *"...also. Quick thing. Do NOT mention last time. He still thinks that was my fault."*

Lore seed for the mode gate's banishment line. **Never explained.** Future PRs can develop "Puck's Exile" as forge mythology if desired.

### 9. Arrival
Puck announces the player using a role-sensitive handoff line (the existing `_puck_handoff_line(role)` helper, kept for now — but called only after `role` is known, which means after the mode gate. So the arrival line is initially generic and we re-render once role is selected. Alternative: defer this beat until after the mode gate. **Engineering decision, not narrative.**)

### 10. Hephaestus reveal
> *"So. You. Puck's been hyping your 'wild idea.' Let's hear it."*

Scripted gruff opener.

### 11. Idea pitch — the hinge
Player types free text. The pitch is sent to Hephaestus as the session's first user message. **⚡ Hephaestus agent responds in character.** Both the player's pitch and Hephaestus's response are written to the session transcript as messages 1 and 2 — the tutorial doesn't end and hand off to a session, it *is* the session's opening exchange. Beat 12 (the mode gate) is also delivered by Hephaestus and lands in the transcript as message 3.

Mneme (the chronicle agent) can later reference this as "the founding pitch."

### 12. Mode gate — in fiction
Hephaestus turns to Puck:
> *"Now. About him. Last time he cost me a week of production. He stays or he goes — your call."*

Player picks **Keep Puck** or **Banish Puck**.

### 13. ⚡ Live Puck reaction
- **Keep Puck:** Live Puck call. Tone: triumphant, gloating at Hephaestus, promising mischief. Fallback: *"HA. You hear that, old man? I'm staying."*
- **Banish Puck:** Live Puck call. Tone: theatrical despair + callback to last time. Fallback: *"Fine. FINE. Banished again. You'll miss me. They always miss me."*

### 14. Reversal hint, diegetic
Final line, regardless of choice (delivered by Hephaestus, gruff but sincere):
> *"The forge keeps its records. `/settings` finds us if you change your mind."*

This makes the escape hatch part of the world rather than a UI footnote.

---

## Section 2 — What the tutorial collects

| Field | When | How |
|---|---|---|
| `display_name` | Always | Beat 4 dialogue |
| `tts_name` | Always | Beat 5 dialogue (optional) |
| Idea pitch | Always | Beat 11 — becomes first session message |
| `experience_mode` | Always | Beat 13 mode gate (set, not asked) |
| Settings cascade | Always | Beat 13 (set, not asked — see Section 3) |
| `title` | Only if Puck kept | Brief post-gate beat |
| `role` | Only if Puck kept | Brief post-gate beat |
| `pronouns` | Only if Puck kept | Brief post-gate beat |

**Rationale:** focused-mode players (banish-Puck) are devs who explicitly opted out of the gamey layer. They get a shorter onboarding — name, pronunciation, idea, done. Title/role/pronouns only matter when maidens address the player personally, which only happens with Puck retained.

The post-gate "tell me how you want to be addressed" beat (only on keep-Puck path) can be delivered by **Kallos** (the style/elegance maiden) — fits her domain and adds another sister-introduction. Open detail for the implementation plan.

---

## Section 3 — Settings cascade + technical integration

### Cascade definitions

**Banish Puck** sets:
```
experience_mode           = focused
romance_enabled           = False
gossip_enabled            = False
romance_nudges_enabled    = False
gossip_nudges_enabled     = False
metrics_tracking_enabled  = False
affinity_tracking_enabled = False
```

**Keep Puck** sets:
```
experience_mode           = gamified
romance_enabled           = False   # ← unchanged; romance stays a separate opt-in
gossip_enabled            = True
romance_nudges_enabled    = True
gossip_nudges_enabled     = True
metrics_tracking_enabled  = True
affinity_tracking_enabled = True
```

**Note on `romance_enabled`:** kept off in both paths. Romance is a deeper commitment than gamified mode, and the existing onboarding already keeps it opt-in. Cupid's *nudges* fire under keep-Puck, but full romance dialogue requires a separate `/settings 4` toggle. This is a deliberate two-step gate to protect players who keep Puck without realizing that opens a romance layer.

### New code surfaces

- `_apply_mode_cascade(mode: Literal["focused", "gamified"]) -> None`
  Single function that flips all seven settings + saves both PlayerProfile and CLISettings. Used by both the onboarding mode gate AND the new `/settings` mode toggle (below). One source of truth.

- `_invoke_agent_live(agent: str, prompt: str, fallback: str, timeout: float = 10.0) -> str`
  Wraps the A2A client call with a timeout and a fallback. Used for all three ⚡ beats (6, 11, 13). Logs failures so we can spot LLM/API issues during onboarding without surprising the player.

- `_run_flight_scene(profile: PlayerProfile) -> tuple[PlayerProfile, str]`
  Runs beats 1–14 and returns the populated profile plus the idea-pitch text (so the caller can feed it into the session as the first message).

### Modifications to existing code

- `hosts/cli/onboarding.py` — `run_onboarding()` is rewritten in terms of the new helpers. Public function signatures (`needs_onboarding`, `run_onboarding`, `increment_session`) stay the same.
- `hosts/cli/commands.py` — `_print_settings_panel` gains a new entry **\[0\] Session Mode: gamified/focused**. Selecting it calls `_apply_mode_cascade()` and prints a diegetic line: *"Puck slips back through the door, grinning."* (focused → gamified) or *"The forge falls quiet."* (gamified → focused).
- `hosts/cli/commands.py` — new slash command `/replay-tutorial` runs `_run_flight_scene()` against the existing profile without resetting anything. Useful for development and replay.
- `hosts/cli/__main__.py` — after `run_onboarding()` returns, the captured idea-pitch text is sent as the session's first message to Hephaestus. (Today the session opens with a hardcoded greeting; that becomes the player's pitch instead.)

### Telemetry / mneme integration

The idea-pitch exchange is appended to the session transcript with a marker (`origin: "first_run_pitch"`) so mneme can reference it as the founding moment. Implementation detail for the plan; not load-bearing for the spec.

### LLM call budget

Per onboarding session, in the worst case:
- 1× Puck name riff (beat 6)
- 1× Hephaestus idea response (beat 11)
- 1× Puck mode-gate reaction (beat 13)

Total: **3 LLM calls** for the new tutorial, vs. 0 today. All three have canned fallbacks, so the onboarding completes even if the A2A bus is down.

---

## Out of scope (follow-up specs)

Each gets its own spec when its turn comes:

1. **Aidos / Aletheia registry parity** — ~~add to
   `AGENT_METADATA`~~ **closed 2026-05-17** (entries with
   canonical Okabe-Ito CVD-safe colors + epithets landed in
   `shared/src/kourai_common/agents.py`; VN `AGENT_CHARS` extended
   in `hosts/vn/kourai_vn/game/script_data.rpy`). Remaining: decide
   CLI surface (slash command? Hephaestus-routed only?). Closes the
   "CLI doesn't know about all 10 agents" gap from the audit.
2. **GUI port of this tutorial** — `hosts/gui/onboarding_ui.py` (611 lines today) gets the same beat structure with pygame-rendered dialogue.
3. **VN port of this tutorial** — Ren'Py scene with Puck sprite, forge background, Hephaestus reveal via sprite-swap. The flagship visual treatment of the flight scene.
4. **Shared-layer cleanup** from the parity audit:
   - ~~GUI's duplicate inline handoff dict in `hosts/gui/maidens.py` →
     import from shared~~ — **closed by
     [#161](https://github.com/ajbarea/kourai-khryseai/pull/161)**
     (2026-05-05). GUI's `maidens.py` now imports from
     `kourai_common.agents` and synthesises the legacy `AGENTS` dict
     from a local color map.
   - `GOSSIP_HINTS` relocation: `agents/vn_bridge.py:72-83` → `shared/`
   - TTS voice config consolidation: GUI's `hosts/gui/tts_helper.py` and shared's `tts_backend.py` → one source of truth

---

## Open questions parked for the implementation plan

- **Beat 9 timing:** does the role-sensitive arrival line render before or after the mode gate? (The line depends on `role`, which is only set on the keep-Puck path.) Two options: defer the arrival flourish until role is known, or use a generic arrival and re-render later. Plan-time decision.
- **Kallos's post-gate appearance:** does she actually speak (live LLM call, +1 to the budget) or does Puck collect title/role/pronouns himself in her name? Plan-time decision.
- **`/replay-tutorial` interactions with `experience_mode`:** if a focused-mode player runs `/replay-tutorial`, do they get the gamified beats (title/role/pronouns)? Probably yes — replaying is for fun, and the cascade re-applies their existing mode at the end. Plan-time decision.
