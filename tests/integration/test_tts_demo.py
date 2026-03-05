"""Demo script for TTS engine with all agent voices.

Run this to hear all five agent voices with their personalities.
"""

import asyncio

from hosts.gui.tts_engine import AGENT_VOICES, VOICE_ROSTER, TTSEngine


async def demo_all_voices():
    """Play demo dialogue with all agent voices."""
    engine = TTSEngine()

    dialogue = [
        ("hephaestus", "System initialized. I am Hephaestus, the forge master. Ready to build."),
        ("metis", "Greetings. I am Metis, keeper of wisdom and strategy."),
        ("kallos", "Hi there! I'm Kallos, bringing beauty and grace to the conversation."),
        ("mneme", "Hello. I am Mneme, the keeper of memories and history."),
        ("techne", "Good day. I am Techne, master of craft and technique."),
        ("dokimasia", "Welcome. I am Dokimasia, testing and validating all things."),
    ]

    print("🎙️  TTS Demo: All Agent Voices\n")
    print("=" * 50)

    for agent_name, text in dialogue:
        voice_key = AGENT_VOICES.get(agent_name, "aria")
        voice_cfg = VOICE_ROSTER[voice_key]

        print(f"\n🗣️  {agent_name.upper()} ({voice_cfg.name})")
        print(f"   {text}")
        print("   [Playing audio...]")

        await engine.speak(text, agent_name=agent_name)

    print("\n" + "=" * 50)
    print("✅ Demo complete!")
    engine.cleanup()


async def demo_custom_voice():
    """Demo using explicit voice selection."""
    engine = TTSEngine()

    print("\n🎙️  Custom Voice Demo\n")
    print("=" * 50)

    # Use Jenny's voice for a friendly message
    text = "This is a friendly message using Jenny's conversational voice!"
    print("\n🗣️  CUSTOM (Jenny)")
    print(f"   {text}")
    print("   [Playing audio...]")

    await engine.speak(text, voice_key="jenny")

    engine.cleanup()


if __name__ == "__main__":
    print("Make sure you have edge-tts and pygame installed:")
    print("  pip install edge-tts pygame\n")

    asyncio.run(demo_all_voices())
    asyncio.run(demo_custom_voice())
