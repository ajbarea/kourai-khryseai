# Kourai Khryseai ElevenLabs Voice Casting Plan

## Goal
Replace the current GUI TTS voices with ElevenLabs voices while preserving each agent's personality, hierarchy, and handoff clarity.

## Recommended model strategy
- Use eleven_flash_v2_5 for live dialogue and low-latency back-and-forth.
- Use eleven_v3 for high-impact lines (victory lines, key handoffs, onboarding moments).
- Keep output format mp3_44100_128 for current workflow compatibility.

## Core casting principles
- One voice family for Core Maidens, one for Companion Spirits, one for Validators.
- Distinct timbre per agent so users can identify speaker before reading text.
- Keep speech speed differences subtle. Avoid cartoon extremes.
- Tune emotional range by role: more expressive for Puck and Kallos, calmer for Aletheia and Aidos.

## Agent-by-agent casting targets

### Core Specialists
- hephaestus
  - Target: low-mid masculine, rough warmth, tired craftsman authority
  - Delivery: deliberate, grounded, dry humor
  - Suggested settings: stability 0.68, similarity 0.78, style 0.25, speed 0.95

- metis
  - Target: poised feminine strategist, crisp diction, subtle superiority
  - Delivery: calm, incisive, lightly teasing
  - Suggested settings: stability 0.72, similarity 0.80, style 0.30, speed 0.92

- techne
  - Target: clean modern feminine, technical confidence, low vocal fry
  - Delivery: fast but articulate, practical and focused
  - Suggested settings: stability 0.66, similarity 0.76, style 0.28, speed 0.96

- dokimasia
  - Target: stern feminine with bite, controlled intensity
  - Delivery: concise, no-nonsense, validator cadence
  - Suggested settings: stability 0.74, similarity 0.80, style 0.22, speed 0.90

- kallos
  - Target: elegant feminine, warm brightness, premium ad-read polish
  - Delivery: lyrical, affectionate, aesthetic framing
  - Suggested settings: stability 0.60, similarity 0.74, style 0.45, speed 1.04

- mneme
  - Target: scholarly feminine, soft resonance, archival gravitas
  - Delivery: precise, reflective, memory-keeper tone
  - Suggested settings: stability 0.76, similarity 0.82, style 0.20, speed 0.92

### Companion Spirits
- puck
  - Target: playful and youthful, quick smile in the voice
  - Delivery: energetic guide without becoming shrill
  - Suggested settings: stability 0.52, similarity 0.70, style 0.48, speed 1.08

- cupid
  - Target: warm intimate feminine, romantic but tasteful
  - Delivery: encouraging, emotionally rich, socially supportive
  - Suggested settings: stability 0.58, similarity 0.75, style 0.50, speed 1.00

### Quality Validators
- aidos
  - Target: restrained neutral-feminine, low dynamics, observant
  - Delivery: minimal affect, high clarity
  - Suggested settings: stability 0.82, similarity 0.84, style 0.10, speed 0.86

- aletheia
  - Target: academic neutral-feminine, evidence-first authority
  - Delivery: measured, careful, citation-ready cadence
  - Suggested settings: stability 0.80, similarity 0.85, style 0.14, speed 0.88

## Fast shortlist to audition first (premade seeds)
Use these as temporary audition seeds before custom voice creation:
- George for hephaestus baseline
- Sarah for metis or mneme baseline
- Daniel for hephaestus alternate baseline
- Charlotte for kallos baseline

Then replace with custom voices designed for your exact persona targets.

## Audition script pack (use same text for every candidate)
Run each candidate through these lines:

1) Command line (authority)
"Pipeline complete. Set down the hammer and review this result."

2) Planning line (strategy)
"We should split this into implementation, verification, and refinement."

3) Flirt/banter line (character)
"Yes, Master... eventually. Let us make it beautiful first."

4) Validator line (precision)
"Claim detected. Provide source and confidence before acceptance."

5) Error line (stress test)
"Connection unstable. Retrying now, maintain context and continue."

## Scoring rubric (1-5 each)
- Role fit: sounds like the intended character
- Intelligibility: clear at normal and fast playback
- Emotional control: expressive without melodrama
- Fatigue resistance: still pleasant after 20+ minutes
- Contrast: clearly distinct from other agents
- Error readability: numbers, filenames, and technical terms stay clear

Keep only voices scoring 24/30 or higher.

## Rollout plan
1) Lock top 2 candidates per agent.
2) Run blind A/B sessions across 10 test prompts.
3) Select winners and freeze settings.
4) Add per-agent voice ids and settings in one mapping file.
5) Keep one emergency fallback voice per tier.

## Implementation note
Store final mapping as a single agent_voice_map config object with:
- agent key
- elevenlabs voice id
- model id
- voice settings
- playback speed multiplier
- fallback voice id
