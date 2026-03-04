"""Advanced TTS demo showcasing March 2026 best practices.

Features demonstrated:
- Real-time volume control
- Pitch and speed modulation
- Audio effect management
- Responsive playback control
- Memory-efficient streaming
"""

import asyncio

from tts_engine import AGENT_VOICES, VOICE_ROSTER, TTSEngine


async def demo_volume_control():
    """Demonstrate volume normalization and control."""
    engine = TTSEngine(master_volume=0.8, enable_effects=True)

    print("\n" + "=" * 60)
    print("🎚️  VOLUME CONTROL DEMO")
    print("=" * 60)

    text = "This is a volume-normalized audio sample with consistent loudness."
    print("\n🗣️  Master Volume: 80%")
    print(f"   Text: {text}")
    print("   [Playing with volume normalization...]")

    await engine.speak(text, voice_key="aria")

    # Adjust volume
    print("\n🗣️  Master Volume: 50%")
    engine.set_master_volume(0.5)
    await engine.speak("This is the same text at fifty percent volume.", voice_key="jenny")

    engine.cleanup()


async def demo_pitch_and_speed():
    """Demonstrate pitch and speed controls."""
    engine = TTSEngine(enable_effects=True)

    print("\n" + "=" * 60)
    print("🎵 PITCH & SPEED MODULATION DEMO")
    print("=" * 60)

    # Normal speech
    text = "I speak at a normal pace with standard pitch."
    print("\n🗣️  NORMAL")
    print("   Speed: 1.0x | Pitch: 1.0x")
    print(f"   Text: {text}")
    await engine.speak(text, voice_key="guy", speed=1.0, pitch=1.0)

    # Faster, slightly higher
    text = "Now I speak faster with elevated pitch for excitement."
    print("\n🗣️  EXCITED")
    print("   Speed: 1.3x | Pitch: 1.2x")
    print(f"   Text: {text}")
    await engine.speak(text, voice_key="guy", speed=1.3, pitch=1.2)

    # Slower, deeper
    text = "And here I speak more slowly with a deeper tone for emphasis."
    print("\n🗣️  EMPHATIC")
    print("   Speed: 0.8x | Pitch: 0.9x")
    print(f"   Text: {text}")
    await engine.speak(text, voice_key="guy", speed=0.8, pitch=0.9)

    engine.cleanup()


async def demo_agent_personalities():
    """Showcase all agent voices with personality-matched settings."""
    engine = TTSEngine(master_volume=0.85, enable_effects=True)

    print("\n" + "=" * 60)
    print("👥 AGENT PERSONALITY VOICES - OPTIMIZED DELIVERY")
    print("=" * 60)

    # Each agent with personality-matched delivery
    personalities = [
        {
            "agent": "hephaestus",
            "text": "Systems online. Ready to forge your vision.",
            "speed": 0.95,
            "pitch": 1.0,
        },
        {
            "agent": "metis",
            "text": "Strategic wisdom at your service.",
            "speed": 0.90,
            "pitch": 1.1,
        },
        {
            "agent": "kallos",
            "text": "Grace and beauty in every interaction!",
            "speed": 1.05,
            "pitch": 1.15,
        },
        {
            "agent": "mneme",
            "text": "All memories preserved with perfect clarity.",
            "speed": 0.92,
            "pitch": 0.95,
        },
        {
            "agent": "techne",
            "text": "Crafted with precision and technical mastery.",
            "speed": 0.93,
            "pitch": 1.05,
        },
        {
            "agent": "dokimasia",
            "text": "Quality assured. Validation complete.",
            "speed": 0.88,
            "pitch": 1.0,
        },
    ]

    for p in personalities:
        agent_name = p["agent"]
        voice_key = AGENT_VOICES.get(agent_name, "aria")
        voice_cfg = VOICE_ROSTER[voice_key]

        print(f"\n🗣️  {agent_name.upper()} ({voice_cfg.name})")
        print(f"   Speed: {p['speed']:.2f}x | Pitch: {p['pitch']:.2f}x")
        print(f"   {p['text']}")
        print("   [Playing optimized audio...]")

        await engine.speak(
            p["text"],
            agent_name=agent_name,
            speed=p["speed"],
            pitch=p["pitch"],
        )

    engine.cleanup()


async def demo_streaming_efficiency():
    """Demonstrate efficient audio streaming with cleanup."""
    print("\n" + "=" * 60)
    print("⚡ STREAMING EFFICIENCY & MEMORY MANAGEMENT")
    print("=" * 60)

    # Create engine with optimized settings
    engine = TTSEngine(enable_effects=True)
    print("\n✓ Engine initialized with low-latency streaming (44.1kHz, 512-byte buffer)")

    # Rapid-fire dialogue to test streaming efficiency
    dialogues = [
        ("aria", "Quick response one."),
        ("jenny", "Quick response two."),
        ("sonia", "Quick response three."),
    ]

    print("📊 Streaming rapid dialogue sequence...")
    for voice_key, text in dialogues:
        await engine.speak(text, voice_key=voice_key)

    print("✓ Efficient memory cleanup completed")
    engine.cleanup()
    print("✓ All temporary files cleaned up")


async def main():
    """Run all advanced demos."""
    print("\n" + "🌟" * 30)
    print("KOURAI KHRYSEAI - ADVANCED TTS SYSTEM (March 2026)")
    print("🌟" * 30)

    try:
        await demo_volume_control()
        await demo_pitch_and_speed()
        await demo_agent_personalities()
        await demo_streaming_efficiency()

        print("\n" + "=" * 60)
        print("✨ All advanced features demonstrated successfully!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        raise


if __name__ == "__main__":
    print("Make sure you have the latest dependencies:")
    print("  pip install pygame-ce>=2.5.0 edge-tts>=0.30.0")
    print()

    asyncio.run(main())
