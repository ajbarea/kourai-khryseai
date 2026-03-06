# Emote SFX — Sound Effect Files

Place `.ogg` files in this directory. The emote SFX engine matches `*emote cues*`
in dialogue text to these files by keyword.

## Required Files

### Physical sounds
| File              | Description                         | Used by           |
|-------------------|-------------------------------------|--------------------|
| `anvil_strike.ogg`| Metallic clang on anvil             | Hephaestus         |
| `hammer_thud.ogg` | Heavy hammer set down               | Hephaestus         |
| `knuckle_crack.ogg`| Knuckle/joint crack                | Dokimasia, Hephaestus |
| `paper_slide.ogg` | Paper sliding across surface        | Metis              |
| `nail_file.ogg`   | Filing/scraping sound               | Metis              |
| `snap.ogg`        | Finger snap                         | Techne             |

### Vocal reactions
| File              | Description                         | Used by           |
|-------------------|-------------------------------------|--------------------|
| `grunt.ogg`       | Gruff short grunt                   | Hephaestus         |
| `sigh.ogg`        | General sigh                        | Kallos, Mneme, Hephaestus |
| `scoff.ogg`       | Dismissive scoff/tsk                | Techne, Kallos, Hephaestus |
| `chuckle.ogg`     | Warm chuckle                        | Hephaestus, Techne |
| `giggle.ogg`      | Light playful giggle                | Metis              |
| `laugh.ogg`       | Confident laugh                     | Techne             |
| `snicker.ogg`     | Smug/knowing snicker                | Mneme              |
| `hum.ogg`         | Contented thoughtful hum            | Kallos             |
| `whisper.ogg`     | Breathy whisper                     | Metis              |
| `clear_throat.ogg`| Throat clear                        | Mneme              |

## Per-agent overrides (optional)

Place agent-specific variants in subdirectories:
```
sfx/hephaestus/sigh.ogg   — gruffer sigh for Hephaestus
sfx/mneme/sigh.ogg         — softer sigh for Mneme
```

The engine checks `sfx/{agent}/{category}.ogg` first, then falls back to `sfx/{category}.ogg`.

## Format guidelines
- **Format**: OGG Vorbis (`.ogg`) — best pygame compatibility
- **Duration**: 0.3–2.0 seconds (short, punchy)
- **Sample rate**: 44100 Hz stereo
- **Loudness**: Normalize to -12 dBFS (SFX volume slider handles the rest)
