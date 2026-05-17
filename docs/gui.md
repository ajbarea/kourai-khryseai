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

### Supporting agents (backend-only in the GUI today)

The Pygame GUI currently renders panels for the six core specialists
above. The four supporting agents — **Puck** (The Jester, tutorial
companion), **Cupid** (The Aspect, romance companion), **Aidos** (anti-slop
validator), and **Aletheia** (research validator) — exist in the agent
backend and are reachable from the CLI / VN, but their GUI portrait
panels aren't wired yet. Puck and Cupid already carry Okabe-Ito
CVD-safe palette entries in `kourai_common.agents.AGENT_METADATA`
ready for portrait rollout; Aidos / Aletheia visual metadata lands when
their panels do. See the [Agents](agents/index.md) page for the full
ten-agent roster.

### Avatar Assets

Avatars live in `assets/avatars/anime/{agent}.png` (one PNG per agent, all
ten covered). PNG with transparency renders best; JPG / JPEG / WebP are
also accepted. The renderer downscales with Lanczos resampling, so the
source image can be any resolution.

---

## Visual Effects

The GUI runs a 120-particle golden-ember background, an agent-switch
crossfade (350 ms), a portrait-panel flash on handoff (200–500 ms,
configurable), and a typewriter effect (10–100 ms/char, press any key to
skip, motion-sensitivity toggle for accessibility).

---

## Text-to-Speech 🎙️

Each agent speaks through a per-agent neural voice. The runtime engine
is [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) via
RealtimeTTS — local, Apache-2.0, ~4 GB system RAM per upstream
guidance on CPU. Edge-TTS is the documented cloud fallback for
environments where Kokoro can't load. Audio plays at 44.1 kHz stereo
with peak + loudness normalization; measured first-chunk latency on
streaming `RealtimeTTS.play()` is ~3s (full latency table in
[ROADMAP M20](../ROADMAP.md#m20--audio-text-synchronization-across-cli--gui--vn)),
and the master volume / per-agent voice override live in
[Configuration → Text-to-Speech](configuration.md#text-to-speech-configuration).

Voice pacing controls the delay before an agent speaks: `INSTANT` /
`FAST` (0.5 s) / `NORMAL` (1.5 s, default) / `SLOW` (3.0 s, light-novel
style) / `CUSTOM`. Thinking pauses and reading speed are independently
toggleable.

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

## Troubleshooting

| Symptom | Fix |
|---|---|
| Window doesn't appear | `uv pip install pygame`; on Linux check display permissions (`xhost +local:`) |
| Avatars don't show | Verify `assets/avatars/anime/{agent}.png` exists, names lowercase, PNG valid |
| Connection errors | `make up` to start Hephaestus; override URL with `--agent http://localhost:10000/` |
| Text rendering issues | Install Inter / Segoe UI / Arial; on Linux `sudo apt install fontconfig` |

## Extending

Adding a new agent: drop the avatar at `assets/avatars/anime/{agent}.png`,
register it in `AGENTS` / `EMOJI_TO_AGENT` / `HANDOFF_LINES` / `VICTORY_LINES`
in `hosts/gui/maidens.py`. Visual constants (colors, dimensions, particle
system) live in `hosts/gui/constants.py`; fonts load in `hosts/gui/__main__.py`.
