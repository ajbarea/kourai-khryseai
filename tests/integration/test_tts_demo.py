"""Demo script for TTS engine with all agent voices.

Run this to hear all five agent voices with their personalities.
"""

import asyncio
import logging

from kourai_common.tts_realtime import AGENT_VOICES, VOICE_ROSTER, RealtimeTTSEngine

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


async def demo_all_voices():
    """Play demo dialogue with all agent voices."""
    engine = RealtimeTTSEngine()

    dialogue = [
        (
            "hephaestus",
            "System initialized. I am Hephaestus, the forge master. Ready to build.",
        ),
        ("metis", "Greetings. I am Metis, keeper of wisdom and strategy."),
        (
            "kallos",
            "Hi there! I'm Kallos, bringing beauty and grace to the conversation.",
        ),
        ("mneme", "Hello. I am Mneme, the keeper of memories and history."),
        ("techne", "Good day. I am Techne, master of craft and technique."),
        ("dokimasia", "Welcome. I am Dokimasia, testing and validating all things."),
    ]

    logger.info("🎙️  TTS Demo: All Agent Voices\n")
    logger.info("=" * 50)

    for agent_name, text in dialogue:
        voice_key = AGENT_VOICES.get(agent_name, "aria")
        voice_cfg = VOICE_ROSTER[voice_key]

        logger.info(f"\n🗣️  {agent_name.upper()} ({voice_cfg.name})")
        logger.info(f"   {text}")
        logger.info("   [Playing audio...]")

        await engine.speak(text, agent_name=agent_name)

    logger.info("\n" + "=" * 50)
    logger.info("✅ Demo complete!")
    engine.cleanup()


async def demo_custom_voice():
    """Demo using explicit voice selection."""
    engine = RealtimeTTSEngine()

    logger.info("\n🎙️  Custom Voice Demo\n")
    logger.info("=" * 50)

    # Use Jenny's voice for a friendly message
    text = "This is a friendly message using Jenny's conversational voice!"
    logger.info("\n🗣️  CUSTOM (Jenny)")
    logger.info(f"   {text}")
    logger.info("   [Playing audio...]")

    await engine.speak(text, voice_key="jenny")

    engine.cleanup()


if __name__ == "__main__":
    logger.info("Requires RealtimeTTS[kokoro] + portaudio runtime libs.\n")

    asyncio.run(demo_all_voices())
    asyncio.run(demo_custom_voice())
