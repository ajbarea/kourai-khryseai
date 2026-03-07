# Text-to-Speech System Architecture

The Kourai Khryseai TTS system delivers neural speech synthesis with personality-matched voices and real-time control.

## Overview

The TTS system combines Microsoft Edge's neural voices with pygame-ce's advanced audio capabilities to create natural, responsive dialogue. Each agent has optimized voice characteristics for personality consistency.

**Key Stats:**
- **44.1 kHz CD-quality stereo** audio
- **<100ms latency** with 512-byte audio buffer
- **6 personality-matched voices** (Aria, Guy, Jenny, Michelle, Sonia)
- **Real-time volume & pitch control** (v2.0+)
- **Automatic loudness normalization** preventing clipping

---

## System Architecture

### Version 1.0 - Core Implementation

Simple, effective speech synthesis pipeline:

```
Text Input
    ↓
edge-tts (neural voice generation)
    ↓
MP3 audio file (temporary)
    ↓
pygame.mixer playback
    ↓
Speaker Output
```

**Components:**
- `tts_engine.py` — Speech generation and playback
- `dialogue_pacing.py` — Response timing and pacing modes
- `tts_gui_integration.py` — GUI integration and event handling
- `tts_settings_config.py` — Settings persistence

**Features:**
- 6 unique agent voices
- 5 pacing modes (INSTANT, FAST, NORMAL, SLOW, CUSTOM)
- Thinking pauses for natural conversation
- Settings persistence to JSON
- Non-blocking async playback

### Version 2.0 (March 2026) - Enhanced Implementation

Professional audio processing pipeline with real-time control:

```
Text Input
    ↓
edge-tts (with prosody control: speed, pitch)
    ↓
Audio Stream
    ↓
╔════════════════════════════════════╗
║  AUDIO PROCESSING PIPELINE         ║
├════════════════════════════════════╤
│  • Normalization (peak + RMS)      │
│  • Volume Control (master volume)  │
│  • Effects (fade in/out)           │
│  • Personality Profiling           │
│  • Quality Assurance               │
╚════════════════════════════════════╝
    ↓
pygame-ce mixer (optimized playback)
    ↓
Speaker Output (Professional Quality)
```

**New v2.0 Features:**
- Real-time master volume control (`set_master_volume()`)
- Pitch modulation parameter (0.5x-2.0x)
- Speed control (0.5x-2.0x) via edge-tts prosody
- Automatic peak normalization
- RMS loudness normalization
- Audio effects library (fade, visualization)
- Personality audio profiles
- pygame-ce integration for enhanced mixer

---

## Core Components

### TTSEngine

**Purpose:** Speech generation and playback engine

**Location:** `hosts/gui/tts_engine.py`

**Key Methods:**
```python
# Initialize with settings
engine = TTSEngine(master_volume=0.8, enable_effects=True)

# Async speech generation and playback
await engine.speak(
    text="Hello, world!",
    agent_name="kallos",           # Optional: auto-select voice
    voice_key="jenny",              # Optional: explicit voice
    speed=1.0,                      # Optional: speed (0.5-2.0)
    pitch=1.0                       # Optional: pitch (0.5-2.0) - v2.0+
)

# Synchronous wrapper
engine.speak_sync(text, agent_name="metis")

# Volume control (v2.0+)
engine.set_master_volume(0.6)

# Lifecycle
engine.stop()
engine.cleanup()
```

**Configuration:**
- Sample rate: 44.1 kHz (fixed)
- Buffer size: 512 bytes (low latency)
- Format: MP3 (efficient compression)
- Channels: 2 (stereo)

### DialoguePacer

**Purpose:** Response timing and pacing control

**Location:** `hosts/gui/dialogue_pacing.py`

**Pacing Modes:**
- `INSTANT` — No delay
- `FAST` — 0.5s delay
- `NORMAL` — 1.5s delay (default)
- `SLOW` — 3.0s delay (light-novel style)
- `CUSTOM` — User-defined timing

**Features:**
- Thinking pauses before responses
- Character-based reading speed calculation
- Async timing utilities

### TTSGUIManager

**Purpose:** Bridges TTS and pacing into GUI event loop

**Location:** `hosts/gui/tts_gui_integration.py`

**Features:**
- Non-blocking async playback
- Event processing with pacing
- Settings panel integration
- Agent voice auto-selection
- Volume and effects control (v2.0+)

### Audio Utilities (v2.0+)

**Purpose:** Professional audio processing

**Location:** `hosts/gui/audio_utils.py`

**Classes:**
- `AudioNormalizer` — Peak and RMS loudness normalization
- `AudioFadeEffect` — Smooth fade-in/fade-out effects
- `AudioVisualizer` — Waveform extraction, loudness estimation
- `PersonalityAudioProfile` — Agent-specific audio characteristics
- `AGENT_PROFILES` — Predefined personality settings

---

## Voice Personality Profiles

### Agent-to-Voice Mapping

| Agent | Voice | Personality | Speed | Pitch |
|-------|-------|-------------|-------|-------|
| 🔨 Hephaestus | Guy | Master Smith | 0.95x | 1.0x |
| 📚 Metis | Aria | Wise Strategist | 0.90x | 1.1x |
| ✨ Kallos | Jenny | Beautiful Grace | 1.05x | 1.15x |
| 📖 Mneme | Michelle | Memory Keeper | 0.92x | 0.95x |
| 🛠️ Techne | Sonia | Technical Expert | 0.93x | 1.05x |
| ✅ Dokimasia | Aria | Quality Validator | 0.88x | 1.0x |

### Voice Characteristics

**Aria (US Female)**
- Tone: Professional, intelligent, authoritative
- Best for: Wisdom, analysis, authority
- Agents: Metis, Dokimasia

**Guy (US Male)**
- Tone: Authoritative, commanding, technical
- Best for: Technical explanations, leadership
- Agents: Hephaestus

**Jenny (US Female)**
- Tone: Friendly, conversational, approachable
- Best for: Encouragement, creativity, warmth
- Agents: Kallos

**Michelle (US Female)**
- Tone: Warm, narrative, storytelling
- Best for: Historical context, memory recall
- Agents: Mneme

**Sonia (GB Female)**
- Tone: Professional, precise, British accent
- Best for: Technical details, craftsmanship
- Agents: Techne

---

## Performance Characteristics

### Latency Profile

| Operation | Latency | Notes |
|-----------|---------|-------|
| Mixer initialization | ~50ms | One-time startup cost |
| Audio generation | 500-2000ms | Depends on text length + network |
| Playback start | ~100ms | After audio generation complete |
| Responsiveness | ~50ms | Per-check latency (acceptable) |

### Memory Usage

| Component | Usage |
|-----------|-------|
| Per-instance | 5-10 MB |
| Temporary storage (audio) | 500 KB - 2 MB |
| Auto-cleanup | Enabled after each playback |

### Audio Quality

| Spec | Value |
|------|-------|
| Sample rate | 44.1 kHz (CD quality) |
| Bit depth | 16-bit |
| Channels | 2 (Stereo) |
| Format | MP3 (compressed) |
| Compression | ~90% smaller than WAV |

---

## Migration Guide: v1.0 → v2.0

??? success "Fully backward compatible"
    All existing v1.0 code continues to work without changes. The new features below are opt-in.

### What's New (Optional)

#### Real-Time Volume Control
```python
# v1.0: Fixed volume at 0.8
engine = TTSEngine()
await engine.speak("Hello")

# v2.0: Dynamic volume control
engine = TTSEngine(master_volume=0.8)
engine.set_master_volume(0.6)  # Adjust anytime
await engine.speak("Hello")
```

#### Pitch and Speed Modulation
```python
# v1.0: Speed only available via voice_cfg
await engine.speak("Hello", agent_name="kallos", speed=1.0)

# v2.0: Speed + pitch with personality matching
await engine.speak(
    "Hello!",
    agent_name="kallos",
    speed=1.3,      # 30% faster
    pitch=1.2       # 20% higher pitch
)
```

#### Enhanced Voice Configuration
```python
# v1.0: Basic voice config
voice_cfg = VoiceConfig("Aria", "en-US-AriaNeural", speed=0.95)

# v2.0: Enhanced with pitch and emotion
voice_cfg = VoiceConfig(
    "Aria",
    "en-US-AriaNeural",
    speed=0.95,
    pitch=1.0,              # NEW
    emotion="default"       # NEW
)
```

#### GUI Settings Panel
```python
# v1.0: Minimal settings
settings = {
    "tts_enabled": True,
    "pacing_mode": "NORMAL"
}

# v2.0: Enhanced with audio controls
settings = {
    "tts_enabled": True,
    "master_volume": 0.8,      # NEW
    "enable_effects": True,    # NEW
    "pacing_mode": "NORMAL"
}
```

### Upgrade Checklist

- [ ] Update pygame to pygame-ce (optional but recommended)
- [ ] Test existing code (should work unchanged)
- [ ] Optionally add volume control: `engine.set_master_volume()`
- [ ] Optionally add pitch parameter in `speak()` calls
- [ ] Review `audio_utils.py` for advanced features
- [ ] Run tests to verify setup

---

## API Reference

### TTSEngine Class

**Constructor:**
```python
TTSEngine(
    temp_dir: Optional[Path] = None,      # Temp audio file directory
    master_volume: float = 0.8,           # Master volume (0.0-1.0)
    enable_effects: bool = True           # Audio processing enabled
)
```

**Methods:**

`async speak(text, agent_name=None, voice_key=None, speed=None, pitch=None)`
- Generate and play speech asynchronously
- Args:
  - `text` (str): Text to speak
  - `agent_name` (str, optional): Agent name for voice auto-selection
  - `voice_key` (str, optional): Explicit voice key from VOICE_ROSTER
  - `speed` (float, optional): Speed multiplier (0.5-2.0)
  - `pitch` (float, optional): Pitch multiplier (0.5-2.0) - v2.0+

`speak_sync(text, agent_name=None, voice_key=None, speed=None, pitch=None)`
- Synchronous wrapper (blocks until complete)

`set_master_volume(volume: float)`
- Set master volume (0.0-1.0) at runtime - v2.0+

`set_on_complete(callback: Callable)`
- Register callback for playback completion

`stop()`
- Stop current playback gracefully

`cleanup()`
- Clean up resources and temporary files

### Voice Roster

```python
VOICE_ROSTER = {
    "aria": VoiceConfig("Aria", "en-US-AriaNeural", 0.95),
    "jenny": VoiceConfig("Jenny", "en-US-JennyNeural", 0.90),
    "michelle": VoiceConfig("Michelle", "en-US-MichelleNeural", 0.92),
    "sonia": VoiceConfig("Sonia", "en-GB-SoniaNeural", 0.93),
    "guy": VoiceConfig("Guy", "en-US-GuyNeural", 0.95),
}

AGENT_VOICES = {
    "hephaestus": "guy",
    "metis": "aria",
    "kallos": "jenny",
    "mneme": "michelle",
    "techne": "sonia",
    "dokimasia": "aria",
}
```

### Audio Utilities (v2.0+)

**AudioNormalizer:**
- `normalize_amplitude(samples, target_level=0.85)` — Peak normalization
- `calculate_rms(samples)` — RMS loudness calculation

**AudioFadeEffect:**
- `apply_fade_in(samples, duration_ms, sample_rate=44100)` — Fade in effect
- `apply_fade_out(samples, duration_ms, sample_rate=44100)` — Fade out effect

**AudioVisualizer:**
- `extract_waveform(samples, num_points=100)` — Waveform data for UI
- `estimate_loudness(samples)` — LUFS-based loudness estimation

**PersonalityAudioProfile:**
- `__init__(name, target_rms, presence_boost_db, warmth_adjustment)`
- `apply_profile(samples)` — Apply personality characteristics

---

## March 2026 Best Practices

### Audio Science
✅ RMS normalization for consistent loudness
✅ Peak normalization to prevent clipping
✅ LUFS-based loudness measurement
✅ Prosody control (pitch, rate)

### Low-Latency Streaming
✅ 512-byte audio buffer (<100ms latency)
✅ 44.1 kHz modern standard
✅ Async-first architecture
✅ Responsive playback control

### Modern Technology Stack
✅ pygame-ce 2.5.0+ (actively maintained)
✅ edge-tts 0.30.0+ (actively developed)
✅ Python 3.12+ (type hints, modern async)

### Professional Quality
✅ Real-time volume adjustment
✅ Personality-matched delivery
✅ Professional audio quality
✅ Responsive user controls

---

## Future Enhancements

- [ ] Real-time audio visualization widget
- [ ] Advanced frequency-domain effects (EQ, reverb)
- [ ] Multi-language prosody models
- [ ] Voice cloning support (GPT-SoVITS integration)
- [ ] Audio streaming from alternative TTS backends
- [ ] SSML markup support for advanced prosody
- [ ] Emotional tone detection and adaptation

---

## Module-Specific References

For implementation details and code structure, see `@hosts/gui/docs/`:
- **TTS_REFERENCE_CARD.md** — API quick reference
- **TTS_FILE_INDEX.md** — Complete file and function inventory
- **AGENT_VOICE_GUIDE.md** — Detailed voice customization
- **TTS_IMPLEMENTATION_CHECKLIST.md** — Step-by-step implementation

---

**Last Updated:** March 4, 2026  
**Version:** 2.0 (March 2026 Implementation)  
**Status:** Production Ready ✨
