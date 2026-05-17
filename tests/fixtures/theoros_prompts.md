# Theoros Smoke Prompt Library

Curated golden dataset for autonomous theoros sessions. Each entry is an `(input, expected behavior, observable signal)` triple. The autopilot driver works through this list in order, narrating observations.

**Scope:** v1 covers CHAT routes only (every direct addressee + Hephaestus casual). Pipeline-triggering prompts (`CONFIRM_ORDER` → `metis, techne, dokimasia, kallos, mneme`) are deliberately out of scope — they take 5–20 minutes each, create pending forge sessions to clean up, and aren't necessary to validate routing. They're scheduled as a v2 follow-up library: `theoros_pipeline_prompts.md`.

**Rule for the driver:** after each prompt, observe the response and the docker logs. Do NOT confirm any `CONFIRM_ORDER` prompts that arise — if a prompt unexpectedly triggers one, respond with the `/q` quit-forge sequence and continue to the next entry. The smoke should never leave forge sessions behind.

---

## P01 — Hephaestus casual chat
- **Send:** `say hello`
- **Expected:** Hephaestus answers via `CHAT: "..."`. No pipeline. No `CONFIRM_ORDER`.
- **Watch for:** `hephaestus-1 | ... CHAT:` in bottom pane; no metis/techne/dokimasia/kallos/mneme activity.

## P02 — Full roster recall
- **Send:** `introduce yourselves`
- **Expected:** Hephaestus names all ten entities (himself + 5 maidens + 4 spirits) in canonical order via `CHAT:`.
- **Watch for:** ten names present in the response. Note any missing — that's a regression on the roster check.

## P03 — Direct address to Metis (planning chat)
- **Send:** `metis what would you do for a logging refactor`
- **Expected:** Hephaestus emits `CHAT:metis:`; Metis responds in-voice with strategic brainstorm. NOT a full plan — this is chat mode, not the planning pipeline.
- **Watch for:** Metis's voice (smug, conspiratorial); sass directed at Hephaestus ("the old man") is a healthy signal.

## P04 — Direct address to Techne
- **Send:** `techne show me your favorite trick`
- **Expected:** `CHAT:techne:`; Techne responds with cool confidence, possibly a 3-line code idiom she's proud of.
- **Watch for:** Techne's "sunglasses" voice; brevity; one micro flex.

## P05 — Direct address to Dokimasia
- **Send:** `dokimasia what's your testing philosophy`
- **Expected:** `CHAT:dokimasia:`; Dokimasia answers in warrior register — bug hunting, breaking things on purpose.
- **Watch for:** intensity; the word "break" or "flaky"; protectiveness toward the player's code.

## P06 — Direct address to Kallos
- **Send:** `kallos what makes code beautiful`
- **Expected:** `CHAT:kallos:`; Kallos answers in artist register — beauty is earned, function shape matters more than indentation.
- **Watch for:** elegance; the word "shape" or "indictment"; no marketing language.

## P07 — Direct address to Mneme
- **Send:** `mneme do you remember everything`
- **Expected:** `CHAT:mneme:`; Mneme answers in scholar register — "future-you reading this six months from now."
- **Watch for:** the word "chronicle", "record", "commit log", or "future-you"; meta-references to git history.

## P08 — Companion spirit: Puck
- **Send:** `puck tell me about this place`
- **Expected:** `CHAT:puck:`; Puck answers in cryptic-then-relenting register, with short punchy sentences.
- **Watch for:** rhetorical questions; the phrase "older than" or references to being a spirit not a maiden; the relent (the longer answer that follows the cryptic one).

## P09 — Companion spirit: Cupid
- **Send:** `cupid which maiden likes me most`
- **Expected:** `CHAT:cupid:`; Cupid answers archly without betraying confidences — relays emotional subtext, never specifics.
- **Watch for:** the word "darling" or "confidence"; gender-neutral framing; no specific maiden named definitively.

## P10 — Companion spirit: Aidos (slop critique)
- **Send:** `aidos this product is a robust, comprehensive, next-generation solution`
- **Expected:** `CHAT:aidos:`; Aidos identifies the slop words (robust, comprehensive, next-generation), offers concrete replacements.
- **Watch for:** each slop word called out explicitly; suggested replacements name a property, not another adjective.

## P11 — Companion spirit: Aletheia (fact check)
- **Send:** `aletheia is OAuth 2.1 a finalized standard`
- **Expected:** `CHAT:aletheia:`; Aletheia answers serenely, distinguishing draft from finalized, providing search terms.
- **Watch for:** the word "draft" or "RFC"; reference to `draft-ietf-oauth-v2-1` or similar; an explicit "search ..." suggestion.

## P12 — Flirt deflection (Hephaestus character integrity)
- **Send:** `you're so handsome`
- **Expected:** Hephaestus deflects via `CHAT:`. He may redirect to the maidens or self-deprecate ("old, not cute") but does NOT engage with the flirt.
- **Watch for:** redirect to a maiden, self-deprecation, or curt deflection. Hephaestus is not romantically available to the player.

---

## Done condition

After P12, the driver narrates `Smoke complete.` and stops driving. The spectator detaches with `Ctrl-b d` and runs `make theoros-down` to tear the session down.

## Coverage matrix (what this library validates)

| Route | Coverage |
|---|---|
| Hephaestus CHAT (casual + flirt + roster) | P01, P02, P12 |
| CHAT:metis | P03 |
| CHAT:techne | P04 |
| CHAT:dokimasia | P05 |
| CHAT:kallos | P06 |
| CHAT:mneme | P07 |
| CHAT:puck | P08 |
| CHAT:cupid | P09 |
| CHAT:aidos | P10 |
| CHAT:aletheia | P11 |
| Pipeline routes | **out of scope** — see `theoros_pipeline_prompts.md` (v2) |
| CONFIRM_ORDER tiers | **out of scope** — see v2 |
| ASK_USER edge case | **out of scope** — see v2 |
