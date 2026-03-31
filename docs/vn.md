# Visual Novel Reference

The Kourai Khryseai Visual Novel is a Ren'Py experience where the Golden Maidens aren't just tools — they're characters with personality, affinity, and romance routes. Built on Ren'Py 8.5.2, connecting to the agent backend through a dedicated `vn-bridge` Docker service (`:10010`).

**Location:** `hosts/vn/kourai_vn/`

---

## Starting the VN

```bash
# From the Ren'Py SDK directory
cd hosts/vn/renpy-8.5.2-sdk
./renpy.sh ../kourai_vn    # Linux/Mac
renpy.exe ..\kourai_vn     # Windows
```

The VN launches, connects to the `vn-bridge` service at `:10010`, and drops you into the forge. The bridge must be running via `docker compose up`.

---

## Architecture

```
┌─────────────────────┐    HTTP (urllib)     ┌──────────────────────┐
│     Ren'Py VN       │ ──── :10010 ──────►  │  vn-bridge (Docker)  │
│  script.rpy         │                       │  agents/vn_bridge.py │
│  screens.rpy        │  ◄── NDJSON ────────  │                      │
│  libs/bridge.py     │                       │  ┌─ A2A client       │
│                     │                       │  └─► Hephaestus      │
│  game/images/       │                       │      (:10000)        │
│    portraits/       │                       │      ├─ Metis  …     │
└─────────────────────┘                       └──────────────────────┘
```

The `vn-bridge` is a standalone Docker service (`docker/host.Dockerfile` with `HOST_TYPE=vn_bridge`) that translates between Ren'Py's synchronous `urllib` calls and Hephaestus's async A2A streaming.

### Bridge HTTP Endpoints

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/health` | GET | Liveness check | `{"status": "ok"}` |
| `/message` | POST | Send message or choice | NDJSON stream |
| `/action` | POST | Profiles, virtues, context resume | Single JSON |
| `/tts` | POST | Text-to-speech (edge-tts) | MP3 bytes |
| `/gossip` | POST | Idle agent flavor text | `{"hint": "...", "line": "..."}` |

### Bridge Protocol

**Player → Bridge (POST /message):**
```json
{"action": "message", "text": "...", "context_id": "uuid", "player_id": "uuid", "project_path": "/abs/path"}
{"action": "choice",  "choice": "selected text", "context_id": "uuid", "player_id": "uuid"}
```

**Bridge → Player (NDJSON stream, one JSON object per line):**
```json
{"action": "status",  "message": "Reading files..."}
{"action": "message", "agent": "techne", "message": "Here's what I found.", "portrait": "neutral", "affinity_delta": 0.02}
{"action": "choice",  "agent": "puck", "prompt": "How do you respond?", "choices": ["Support her", "Change the subject"]}
```

The Ren'Py client (`libs/bridge.py`) spawns daemon threads that stream NDJSON lines into an inbox queue. The main Ren'Py loop polls via `get_message(timeout=0.05)`.

### Pickle Safety

Ren'Py saves game state via Python pickle. The bridge uses `python hide` blocks and `__getstate__`/`__setstate__` to avoid pickling thread/connection objects:

```python
# CORRECT — hidden namespace, not saved
init python hide:
    from game.libs.bridge import RenPyBridge
    bridge = RenPyBridge()

# WRONG — crashes on save
# $ bridge = RenPyBridge()
```

---

## Screens

### In-Game Overlays

| Screen | Purpose | Status |
|--------|---------|--------|
| `affinity_hud` | Top-right HUD: 6 agents + scores + heart tiers | Done |
| `gossip_bubble` | Bottom-left flavor text from idle agents (8s auto-dismiss) | Done |
| `thinking` | Bottom-center "⚒ [status]" with 0.4s refresh | Done |
| `agent_choice` | Modal choice dialog with forge styling | Done |
| `agent_portrait` | Left-side portrait display (dramatic rise) | Done |
| `forge_journal` | Virtue scores, patron agents, session deltas | Placeholder |
| `project_selection` | Directory browser for project root | Placeholder |

### Standard Menus

All standard Ren'Py menus are themed with the forge aesthetic (warm parchment, gold accents, charcoal backgrounds). The quick menu adds **Journal** and **Project** buttons alongside the standard Back/History/Skip/Auto/Save/Load/Prefs.

---

## Affinity System

The VN tracks player-agent affinity in real-time with a persistent HUD:

| Tier | Name | Range | Visual | Unlocks |
|------|------|-------|--------|---------|
| 1 | Professional | 0.0–0.4 | 💛 | Basic work mode |
| 2 | Friendly | 0.4–0.65 | 💛💛 | Casual chat, jokes, gossip |
| 3 | Close | 0.65–0.85 | 💛💛💛 | Special moments, jealousy |
| 4 | Intimate | 0.85–1.0 | 💛💛💛💛 | Confession, romance |

Affinity starts at 0.5 and increases +0.02 per interaction (client-side). The backend will eventually send `affinity_delta` events to override/sync.

---

## Gossip System

Every 3 turns, a random idle agent (not the one you're currently talking to) shares personality-driven flavor text:

```
💬 Kallos: "Techne thinks she's the star of the forge. She's wrong — I am."
💬 Mneme: "I've been documenting everything. Your story is more interesting than you think."
💬 Dokimasia: "Don't mind me. Just... making sure everything's up to standard."
```

Auto-dismisses after 8 seconds.

---

## Portrait System

6 of 18 portraits are complete (neutral state). The system uses a fallback chain:

1. Requested state (e.g., `vulnerable`) → try loading `{agent}_vulnerable.png`
2. Fallback to `neutral` → try loading `{agent}_neutral.png`
3. Fallback to `None` → skip portrait display entirely

Portraits live in `game/images/portraits/` and use a warm forge aesthetic.

---

## Color Scheme

The VN uses a warm forge-inspired palette:

| Element | Color | Hex |
|---------|-------|-----|
| Text on dialogue | Dark brown | `#3A2E1F` |
| Accent / gold | Gold | `#D4AF37` |
| Dialogue background | Warm cream | `#F5F0E1` |
| Page background | Dark charcoal | `#1A1A1A` |
| Hephaestus | Warm gold | `#D4A017` |
| Techne | Teal | `#17A2B8` |
| Kallos | Magenta | `#D946EF` |
| Metis | Indigo | `#4C6EF5` |
| Dokimasia | Steel gray | `#6C757D` |
| Mneme | Burgundy | `#B73E1D` |
| Puck | Amber | `#F59E0B` |
| Cupid | Coral pink | `#FB7185` |

Style direction: Warm gold (ornate, cream background, red leaf accents).

---

## Agent Epithets

Displayed under agent names in dialogue:

| Agent | Epithet |
|-------|---------|
| Hephaestus | Master of the Forge |
| Techne | Artisan of Code |
| Kallos | Eye of Elegance |
| Metis | Architect of Intent |
| Dokimasia | Guardian of Standards |
| Mneme | Keeper of Memory |

---

## Save/Load

Save slots display:
- Agent portrait thumbnail (0.25 zoom)
- Timestamp
- Custom save note (agent's epithet)

The bridge reconnects to `:10010` on load — only the bridge URL and context state are pickled. A `resume` action via `/action` re-sends `context_id` to restore conversation state.

---

## Troubleshooting

### Bridge won't connect
- Ensure Docker is running: `docker compose up`
- Check that `vn-bridge` is healthy: `curl http://localhost:10010/health`
- Check that Hephaestus is up: `docker compose logs vn-bridge`

### Save crashes
- Never store thread/connection objects in Ren'Py store variables
- Always use `python hide` blocks for non-picklable objects
- Delete `game/cache/` if bytecode is stale

### Portraits don't show
- Verify PNG files in `game/images/portraits/`
- File names must match `{agent_id}_{state}.png` exactly (lowercase)
- Check `PORTRAIT_STATES` validation in `script.rpy`

### Performance
- Call `renpy.free_memory()` between major transitions
- Avoid loading all 18+ portraits simultaneously
- `thinking` screen refreshes every 0.4s — minimize layered elements
