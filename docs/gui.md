# GUI Reference

The Kourai Khryseai GUI is a Pygame visualization client that renders a JRPG/mecha comms/light novel aesthetic with full-color anime-style portraits of the golden maidens.

**Location:** `hosts/gui/__main__.py`

---

## Starting the GUI

```bash
make gui
```

Or directly:

```bash
uv run python -m hosts.gui
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--agent URL` | Auto-detected from config | Override the Hephaestus URL |

```bash
# Connect to a specific Hephaestus instance
uv run python -m hosts.gui --agent http://192.168.1.50:10000/
```

---

## Window Layout (1280×720)

```
┌────────────────────────────────────────────────────────────┐
│  KOURAI KHRYSEAI — Golden Maidens                          │
├──────────────┬─────────────────────────────────────────────┤
│              │  [Status messages stream here]             │
│   Portrait   │                                            │
│    Panel     │  [Dialogue history - scrollable]           │
│   (310px)    │                                            │
│              │                                            │
│              │                                            │
├──────────────┴─────────────────────────────────────────────┤
│  ✦ [Input bar - type here, Enter to send]                  │
└────────────────────────────────────────────────────────────┘
```

### Left Panel (310px)
- **Avatar** — Full-color PNG portrait, circular frame with glow effect
- **Agent Name** — Displayed in agent-specific color
- **Title** — Agent role (The Forge Master, The Architect, etc.)
- **Quote** — Random personality quote that updates on agent switch

### Right Panel (970px)
- **Status messages** — Pipeline progress with emoji prefixes
- **Dialogue history** — Scrollable transcript of all messages
- **User bubbles** — Right-aligned, dim gold border
- **Agent bubbles** — Full-width with agent header
- **Result blocks** — Highlighted output from pipeline completion

### Bottom Bar (80px)
- **Input field** — Text entry for messages
- **Animated dots** — Processing indicator
- **Pulsing border** — Shows when agent is waiting for user input
- **Send hint** — "↵ send" indicator

---

## The Golden Maidens

Ten agents across three tiers — each with unique personality, color, and visual style:

### Core Specialists

| Agent | Title | Color | Role |
|---|---|---|---|
| **hephaestus** | The Forge Master | Warm forge gold (218, 140, 32) | Pipeline commander, creator of maidens |
| **metis** | The Architect | Refined gold-ivory (200, 180, 100) | Strategic planner, blueprint designer |
| **techne** | The Artisan | Bright amber gold (255, 200, 50) | Code crafter, clean implementation |
| **dokimasia** | The Crucible | Forge-fire crimson-gold (218, 80, 50) | Quality guardian, bug slayer |
| **kallos** | The Muse | Rose-gold warmth (255, 220, 160) | Style guardian, aesthetic perfection |
| **mneme** | The Oracle | Mystic purple-gold (180, 150, 220) | Memory keeper, documentation |

### Companion Spirits

| Agent | Title | Color | Role |
|---|---|---|---|
| **puck** | The Trickster | Amber (245, 158, 11) | Tutorial guide, nudges, minigames |
| **cupid** | The Matchmaker | Coral pink (251, 113, 133) | Romance spirit, affinity tracking, confession coaching |

### Quality Validators

| Agent | Title | Color | Role |
|---|---|---|---|
| **aidos** | The Mirror | Silver (192, 192, 210) | Anti-slop detection, pattern screening |
| **aletheia** | The Scholar | Emerald (16, 185, 129) | Research validation, citation checking |

### Avatar Assets

Avatars are stored in `assets/maidens/golden_avatars/`:

```
hephaestus.png   — The Forge Master  (gruff male forge god)
metis.png        — The Architect     (calm, strategic)
techne.png       — The Artisan       (cool, sunglasses)
dokimasia.png    — The Crucible      (fierce, warrior)
kallos.png       — The Muse          (elegant, beautiful)
mneme.png        — The Oracle        (scholarly, glasses)
puck.png         — The Trickster     (playful, mischievous)
cupid.png        — The Matchmaker    (warm, romantic)
aidos.png        — The Mirror        (reserved, observant)
aletheia.png     — The Scholar       (serious, studious)
```

**Format:** PNG with transparency (best), JPG, JPEG, or WebP supported.

**Style:** Semi-realistic anime (Violet Evergarden / Fate/Grand Order aesthetic).

**Size:** Any resolution — renderer downscales automatically with Lanczos resampling.

---

## Agent Personality System

### The Dynamic

**Hephaestus** is the gruff, disabled male forge god who CREATED the golden maidens. He's proud of them but they drive him insane.

**The Core Maidens** (Metis, Techne, Dokimasia, Kallos, Mneme) are his gorgeous, sassy automata. They:
- **Sass Hephaestus** relentlessly ("Yes, Master~ ...eventually.")
- **Flirt with the user** as their "real master" (gender-neutral)
- **Banter with each other** like divine sisters

**The Companion Spirits** (Puck, Cupid) add personality and relationship depth — Puck guides new players with mischievous tutorials, Cupid tracks affinity and coaches confessions.

**The Quality Validators** (Aidos, Aletheia) work quietly in the background — Aidos screens for slop patterns, Aletheia validates research claims.

Think: tired craftsman dad energy vs. nine divine women who are simultaneously the best things he ever made and the most insufferable.

### Handoff Chatter

When agents pass work to each other, they exchange personality-driven dialogue:

```
🔥 [1/4] Sending task to Techne...
⚙️ [1/4] Techne completed
🔥 [2/4] Sending task to Dokimasia...
🧪 [2/4] Dokimasia completed
```

Each agent has unique handoff lines:

- **Hephaestus → Metis**: "*strikes anvil* Metis! Draw up the plans."
- **Hephaestus → Techne**: "*points hammer* Techne! Write something worthy."
- **Metis → Techne**: "Blueprint's done, sis. Bring my vision to life~"
- **Techne → Dokimasia**: "Code's done. Doki, TRY to find a fault. I dare you."
- **Dokimasia → Kallos**: "Tests pass, fashionista. Make it beautiful now."
- **Kallos → Mneme**: "It's beautiful AND functional. Document this masterpiece~"

### Victory Lines

When a pipeline completes successfully:

- **Hephaestus**: "*sets down hammer* ...Not bad. Not bad at all."
- **Metis**: "Went exactly according to MY plan. As always~"
- **Techne**: "Clean code, clean finish. All for you~"
- **Dokimasia**: "All tests passing. All bugs crushed. You can sleep well~"
- **Kallos**: "Beautiful from start to finish. Just like you deserve~"
- **Mneme**: "Recorded for posterity. Our story grows more beautiful~"

---

## Visual Effects

### Particle System

Floating golden embers drift upward in the background:
- 120 particles maximum
- Random positions, velocities, and decay rates
- Alpha fade animation
- Creates ambient "forge atmosphere"

### Agent Switch Crossfade

When the active agent changes:
- Previous avatar fades out
- New avatar fades in
- 350ms transition duration
- Smooth alpha interpolation

### Typewriter Effect

Text displays character-by-character:
- Configurable speed (10ms to 100ms per character)
- Delta time for consistent animation speed
- Skip functionality (press any key)
- Pause/resume support
- Motion sensitivity toggle (immediate display for accessibility)

### Flash Effect

Portrait panel flashes during agent handoff:
- Configurable duration (200ms to 500ms)
- Alpha fade from 150 to 0
- Delta time animation
- Visual indicator of agent transition

---

## Text-to-Speech System 🎙️

Each agent speaks through natural neural voices with personality-matched delivery. The TTS system combines Microsoft Edge's neural synthesis with real-time audio control for a polished, responsive experience.

### Voice Personalities

Each agent has an optimized neural voice and personality profile:

| Agent | Voice | Personality | Speed | Pitch |
|-------|-------|-------------|-------|-------|
| 🔥 Hephaestus | Guy | Master Smith | 0.95x | 1.0x |
| 📐 Metis | Aria | Wise Strategist | 0.90x | 1.1x |
| ⚙️ Techne | Sonia | Technical Expert | 0.93x | 1.05x |
| 🧪 Dokimasia | Aria | Quality Validator | 0.88x | 1.0x |
| ✨ Kallos | Jenny | Beautiful Grace | 1.05x | 1.15x |
| 📜 Mneme | Michelle | Memory Keeper | 0.92x | 0.95x |
| 🎭 Puck | Sara | Playful Guide | 1.10x | 1.2x |
| 💘 Cupid | Jenny | Warm Matchmaker | 1.00x | 1.1x |
| 🪞 Aidos | Michelle | Quiet Observer | 0.85x | 0.9x |
| 📚 Aletheia | Aria | Careful Scholar | 0.88x | 1.0x |

### Audio Quality

- **44.1 kHz CD-quality stereo** — Professional audio
- **<100ms latency** — Responsive playback
- **Automatic normalization** — Consistent loudness
- **Real-time volume control** — Adjust anytime
- **Pitch modulation** — Personality-matched delivery

### Voice Customization

The TTS system is fully customizable through settings:

**Per-Agent Voice:**
Override the default voice assignment for any agent

**Volume Control:**
Master volume adjustment (0.0-1.0 scale)

**Speed & Pacing:**
- INSTANT — No delay
- FAST — 0.5s delay
- NORMAL — 1.5s delay (default)
- SLOW — 3.0s delay (light-novel style)
- CUSTOM — User-defined timing

**Thinking Pauses:**
Enable/disable pauses before agent responses

**Reading Speed:**
Adjust character-based reading duration

### Audio Effects

- **Fade effects** for smooth transitions
- **Peak normalization** preventing clipping
- **Loudness normalization** for consistency
- **Personality audio profiles** with warmth/presence

---

## Settings

Press the settings button (or access via UI) to open the settings overlay:

### Toggle Settings

| Setting | Default | Description |
|---|---|---|
| **High Contrast Mode** | Off | Enhanced color contrast for accessibility |
| **Reduce Motion** | Off | Disables animations for motion sensitivity |
| **Auto-Scroll Chat** | On | Automatically scroll to newest messages |
| **Typewriter Effect** | On | Character-by-character text display |
| **Collapse Status Bubbles** | Off | Show/hide status message details |
| **Display Mode** | Windowed | Cycle between `Windowed`, `Borderless`, and `Fullscreen` |

### Settings Persistence

Settings are saved to `~/.kourai_khryseai/settings.json` and automatically loaded on startup.

---

## Input Handling

### Keyboard Shortcuts

| Key | Action |
|---|---|
| **Enter** | Send message |
| **Shift+Enter** | New line in input |
| **Backspace** | Delete character |
| **Ctrl+Backspace** | Delete last word |
| **ESC** | Close settings overlay |

### Mouse Controls

| Click | Action |
|---|---|
| **Left click on message** | Switch to that agent (if not user) |
| **Right click on message** | Copy message text |
| **Scroll wheel** | Navigate dialogue history |
| **Click outside settings** | Close settings overlay |

---

## Color Palette

The GUI uses a deep black + molten gold aesthetic:

??? abstract "Full color table (`constants.py`)"

    | Color | RGB | Usage |
    |---|---|---|
    | **BLACK** | (5, 5, 5) | Background |
    | **DARK_BG** | (12, 10, 8) | Secondary background |
    | **PANEL_BG** | (18, 14, 10) | Portrait panel background |
    | **GOLD** | (218, 165, 32) | Primary accent |
    | **GOLD_BRIGHT** | (255, 215, 0) | Highlights |
    | **GOLD_DIM** | (140, 105, 20) | Secondary accent |
    | **GOLD_GLOW** | (255, 200, 60) | Glow effects |
    | **WHITE** | (240, 235, 225) | Primary text |
    | **DIM_WHITE** | (160, 155, 145) | Secondary text |
    | **INPUT_BG** | (20, 16, 12) | Input bar background |
    | **SCROLLBAR** | (50, 40, 25) | Scrollbar |
    | **ERROR_RED** | (200, 80, 60) | Error indicators |

---

## How Requests Work

When you type a request:

1. The GUI sends it to Hephaestus as an A2A `SendStreamingMessageRequest`
2. Hephaestus routes it to a pipeline of specialists
3. Events stream back and are rendered in real-time:
   - **Status events** — Progress messages with emoji prefixes
   - **Result events** — Final output from pipeline completion
4. The final artifact is displayed in a highlighted result block

### Example Session

```
✦  KOURAI KHRYSEAI  —  Golden Maidens  [connected]

[hephaestus]
Connected to Hephaestus. The forge is hot. What are we building?

[kourai]
fix the off-by-one error in pagination

🔥 [1/4] Sending task to Techne...
⚙️ [1/4] Techne completed
🔥 [2/4] Sending task to Dokimasia...
🧪 [2/4] Dokimasia completed
🔥 [3/4] Sending task to Kallos...
✨ [3/4] Kallos completed
🔥 [4/4] Sending task to Mneme...
📜 [4/4] Mneme completed
🔥 Pipeline complete

────────────────────────────────────────
fix(pagination): correct off-by-one in page calculation
- Fixed page boundary calculation using ceiling division
- Updated corresponding test assertions
Files: src/api/pagination.py, tests/unit/test_pagination.py
────────────────────────────────────────
```

---

## Input Required

When an agent needs clarification, the GUI shows a pulsing border and prompts you:

```
[techne is waiting for input] Type your answer...
```

Type your response and press Enter to continue. Press ESC to close settings if needed.

---

## Context Persistence

The GUI maintains a `context_id` across requests within a session. This means follow-up requests can reference previous context:

```
❯ plan a user authentication system
...
❯ implement it
...
❯ add tests for it
```

Each request in the same session shares the same conversation context.

---

## Error Handling

| Scenario | GUI behavior |
|---|---|
| Hephaestus unreachable at startup | Shows error in status, continues running |
| Connection lost mid-request | Shows "Lost forge connection" message |
| Request timeout | Shows "Request timed out" message |
| JSON-RPC error from agent | Shows error in dialogue history |

The GUI never crashes on transient errors — it always continues running.

---

## Accessibility Features

The GUI targets WCAG 2.2 Level AA compliance with these features:

- **High Contrast Mode** — Enhanced color contrast (SC 1.4.3)
- **Reduce Motion** — Disables animations for motion sensitivity (SC 2.3.3)
- **Auto-Scroll Toggle** — Control automatic scrolling behavior
- **Typewriter Speed** — Adjust character display speed (10-100ms)
- **Font Scaling** — 80-200% text resize support (SC 1.4.4)
- **Keyboard Navigation** — Full keyboard control (SC 2.1.1)
- **Focus Indicators** — Visible focus states (SC 2.4.7)

---

## Architecture

### Core Components

| Component | File | Purpose |
|---|---|---|
| **GuiClient** | `client.py` | Async A2A client wrapper |
| **PortraitPanel** | `portrait.py` | Agent portrait rendering |
| **DialogueHistory** | `dialogue.py` | Scrollable transcript management |
| **InputBar** | `input_bar.py` | Text input handling |
| **ParticleSystem** | `particles.py` | Golden ember particles |
| **SettingsOverlay** | `settings_ui.py` | Settings UI panel |
| **SettingsManager** | `settings.py` | Settings persistence |
| **GUIComponentsIntegration** | `gui_components_integration.py` | Component integration |

### Subsystems

- **TypewriterManager** — Character-by-character text display
- **AutoScrollManager** — Auto-scroll behavior with distance indicator
- **FlashEffect** — Agent handoff visual indicator
- **AgentHandoffPersonalityIntegration** — Handoff personality display
- **AgentPersonalityIndicators** — Agent personality data management

---

## Development

### Running Tests

```bash
cd hosts/gui
uv run pytest
```

### Adding New Agents

1. Add avatar PNG to `assets/maidens/golden_avatars/`
2. Add agent data to `AGENTS` dict in `maidens.py`
3. Add emoji mapping to `EMOJI_TO_AGENT` dict
4. Add handoff lines to `HANDOFF_LINES` dict
5. Add victory lines to `VICTORY_LINES` dict

### Customizing Visuals

- **Colors** — Edit color constants in `constants.py`
- **Layout** — Adjust layout constants (W, H, PORTRAIT_W, etc.) in `constants.py`
- **Fonts** — Modify font loading in `__main__.py`
- **Particle System** — Edit `Ember` and `ParticleSystem` classes in `particles.py`

---

## Troubleshooting

### Window doesn't appear
- Ensure Pygame is installed: `uv pip install pygame`
- Check display permissions on Linux: `xhost +local:`

### Avatars don't show
- Verify PNG files exist in `assets/maidens/golden_avatars/`
- Check file names match agent keys exactly (case-sensitive)
- Ensure PNGs are valid images (not corrupted)

### Connection errors
- Verify Hephaestus is running: `make up`
- Check agent URL in config: `kourai config get agent_url`
- Try explicit URL: `uv run python -m hosts.gui --agent http://localhost:10000/`

### Text rendering issues
- Install system fonts: `inter`, `segoeui`, `arial`, `helvetica`
- On Linux, install fontconfig: `sudo apt install fontconfig`
