# Setting Concepts — Background Generation Prompts

Generation prompts for the VN's background art. Keep these alongside the
PNGs so a future regeneration pass can reproduce or iterate on the look.

The VN's `warm forge aesthetic` relies on deep charcoal (`#1A1A1A`), warm
cream (`#F5F0E1`), and gold accents — canonical gold is `#C9944A` with
highlight `#F1D2A1` and shadow `#AA771C`. Each agent has a distinct accent
color (Amber, Indigo, Magenta, Teal, Ember, Gray) that must pop against
the background, so the background itself stays warm-dominant and limited.

Because players stare at this for hours, avoid the stereotypical "grimy,
sooty blacksmith forge with harsh orange lava." The target feel is
**divine, ethereal, and magical** — a place worthy of Greek gods and
advanced automaton agents.

## Current — Divine Forge-Atelier (`forge_hades.png`)

The shipped background. Asymmetric composition with warm forge upper-left
and cool indigo window upper-right — the warm/cool tension visually
echoes the Hephaestus ↔ Metis handoff without depicting either. Empty
center-bottom flagstones reserve space for standing sprites.

**Prompt:**

> A wide 16:9 cinematic visual-novel background depicting the interior of
> a divine forge-atelier carved into the side of a moonlit mountaintop.
> **Upper-left:** a great stone forge with a contained, warm golden fire
> — soft spill-light bathes the left wall and flagstones in honey-gold.
> **Upper-right:** a tall arched window of leaded copper and obsidian
> frames a deep indigo starry sky with slowly drifting constellations and
> a single pale moon; moonlight streams diagonally down-and-left, meeting
> the forge glow near the center. **Midground left:** an oak drafting
> table half-lit by firelight, scattered with unrolled parchment
> blueprints, brass calipers, a gleaming astrolabe. **Midground right:**
> leatherbound tomes and labeled bronze jars on deep-shadowed shelves,
> receding into soft focus. Ancient Greek iconography — Doric column
> edges, laurel friezes, faint relief carvings of craftsmen-gods — hints
> along the stone walls. Flagstone floor in the foreground kept visually
> quiet — empty, waiting for standing characters. **Style:** stylized
> painterly 2D illustration, digital painting with confident thick
> brushwork, bold clean silhouettes, high-contrast shadow shapes, warm
> atmospheric volumetric light rays, slight depth-of-field blur on
> background elements so foreground sprites will pop. Inspired by classic
> animated feature backgrounds and high-end graphic-novel interior
> painting. **Palette:** deep charcoal, honeyed amber-gold (#C9944A),
> warm cream highlights (#F1D2A1), with cool indigo and soft teal only
> as accent in the window and deep shadows — warm-dominant, limited,
> harmonious. **Mood:** serene, magical, lived-in — as if the owners
> have just stepped away for a moment. No people, no figures, no text,
> no UI. Editorial game-background quality, cinematic, high detail,
> 16:9, 1920×1080 native.

**Negative prompt:**

> characters, people, figures, humans, gods, silhouettes, portraits,
> text, watermark, logo, signature, UI, HUD, dialogue box, borders,
> picture frames, bright red, harsh orange lava, symmetrical centered
> composition, cluttered foreground, busy center-bottom, square aspect
> ratio, grimy industrial blacksmith, cartoon, anime, photorealistic,
> 3D render, CGI.

### Why this composition works

1. **Asymmetric warm/cool balance.** Forge upper-left (amber) vs window
   upper-right (indigo) mirrors the two lead agents without literally
   depicting them. Accent colors in agent sprites pop against the
   complementary quadrant.
2. **Negative space reserved for sprites.** Center-bottom is deliberately
   quiet flagstone — the dramatic moonlight shaft acts as a natural
   divider between left and right sprite slots.
3. **Lived-in props.** Drafting table with blueprints, tomes, bronze
   jars — communicates "the gods just stepped out" rather than reading
   as an empty stage set.
4. **Palette-locked to our tokens.** `#C9944A` and `#F1D2A1` are called
   out by hex so gen tools with color conditioning lean our amber, not
   generic Hollywood-bronze.
5. **Depth-of-field blur.** Background elements intentionally soft so
   crisp sprites pop against them without fighting for attention.

### Avoid third-party-content guardrails

Earlier iterations named a specific studio / artist / game franchise for
the style reference. Some gen tools refuse those on IP grounds. The
formal descriptors in the prompt above (*"stylized painterly 2D
illustration, digital painting with confident thick brushwork, bold
clean silhouettes, high-contrast shadow shapes"*) achieve the same
aesthetic without tripping filters.

## Deprecated drafts

Two earlier concepts (`forge_celestial.png` — cavernous stone hall with
floating gears; `forge_ethereal.png` — marble courtyard with sunlit
pillars) were generated and deleted on 2026-04-24. Both were
symmetrical, square-aspect, and put visual density exactly where
character sprites stand. Superseded by `forge_hades.png`.
