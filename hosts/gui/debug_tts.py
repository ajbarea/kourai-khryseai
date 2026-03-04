#!/usr/bin/env python3
"""
TTS Engine Debugging & Validation Script
Run this to verify edge-tts + pygame mixer integration is working.
"""

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def check_dependencies():
    """Verify all required dependencies are installed."""
    logger.info("=== CHECKING DEPENDENCIES ===")
    deps = {
        "pygame": "pygame",
        "PIL": "pillow",
        "edge_tts": "edge-tts",
    }

    missing = []
    for name, pkg in deps.items():
        try:
            __import__(name)
            logger.info(f"✓ {pkg}")
        except ImportError:
            logger.error(f"✗ {pkg} NOT FOUND")
            missing.append(pkg)

    if missing:
        logger.error(f"Missing packages: {', '.join(missing)}")
        logger.error(f"Install with: pip install {' '.join(missing)}")
        return False
    return True


def check_audio_converter():
    """Check if ffmpeg or avconv is available."""
    logger.info("\n=== CHECKING AUDIO CONVERTER ===")
    for converter in ["ffmpeg", "avconv"]:
        try:
            result = subprocess.run([converter, "-version"], capture_output=True, timeout=2)
            if result.returncode == 0:
                logger.info(f"✓ {converter} found")
                return converter
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    logger.warning("✗ No audio converter (ffmpeg/avconv) found!")
    logger.warning("  This is REQUIRED for MP3→WAV conversion")
    logger.warning("  Install ffmpeg from https://ffmpeg.org or via your package manager")
    return None


def check_pygame_mixer():
    """Test pygame mixer initialization."""
    logger.info("\n=== CHECKING PYGAME MIXER ===")
    try:
        import pygame

        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        logger.info("✓ Pygame mixer initialized successfully")
        pygame.mixer.quit()
        return True
    except Exception as e:
        logger.error(f"✗ Pygame mixer init failed: {e}")
        return False


async def test_edge_tts():
    """Test edge-tts speech generation."""
    logger.info("\n=== TESTING EDGE-TTS ===")
    try:
        import edge_tts

        text = "Hello world, this is a test."
        temp_file = Path("/tmp/test_edge_tts.mp3")

        logger.debug(f"Generating speech for: '{text}'")
        communicate = edge_tts.Communicate(text, "en-US-AriaNeural", rate="+0%")
        await communicate.save(str(temp_file))

        if temp_file.exists():
            size_kb = temp_file.stat().st_size / 1024
            logger.info(f"✓ Generated MP3: {size_kb:.1f} KB")
            temp_file.unlink()
            return True
        else:
            logger.error("✗ MP3 file not created")
            return False
    except Exception as e:
        logger.error(f"✗ Edge-TTS failed: {e}", exc_info=True)
        return False


async def test_full_pipeline():
    """Full end-to-end TTS + mixer test."""
    logger.info("\n=== FULL PIPELINE TEST ===")
    try:
        import edge_tts
        import pygame

        # Step 1: Generate audio
        logger.debug("Step 1: Generating MP3 with edge-tts...")
        temp_mp3 = Path("/tmp/test_pipeline.mp3")
        communicate = edge_tts.Communicate("Testing one two three", "en-US-GuyNeural", rate="+0%")
        await communicate.save(str(temp_mp3))

        if not temp_mp3.exists():
            logger.error("✗ MP3 generation failed")
            return False
        logger.info(f"✓ MP3 generated ({temp_mp3.stat().st_size} bytes)")

        # Step 2: Convert to WAV
        logger.debug("Step 2: Converting MP3→WAV...")
        temp_wav = Path("/tmp/test_pipeline.wav")
        result = subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(temp_mp3),
                "-acodec",
                "pcm_s16le",
                "-ar",
                "44100",
                "-ac",
                "2",
                str(temp_wav),
                "-y",
            ],
            capture_output=True,
            timeout=10,
            text=True,
        )

        if result.returncode != 0:
            logger.warning(f"Conversion warning: {result.stderr[:200]}")

        if not temp_wav.exists():
            logger.warning("WAV not created, testing MP3 playback directly...")
            playback_file = temp_mp3
        else:
            logger.info(f"✓ WAV generated ({temp_wav.stat().st_size} bytes)")
            playback_file = temp_wav

        # Step 3: Play audio
        logger.debug("Step 3: Playing audio with pygame mixer...")
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        sound = pygame.mixer.Sound(str(playback_file))
        logger.info(f"✓ Sound loaded ({sound.get_length():.2f}s)")

        sound.set_volume(0.8)
        sound.play()
        logger.info("Playing sound (you should hear audio)...")

        # Wait for playback
        while pygame.mixer.get_busy():
            await asyncio.sleep(0.1)

        logger.info("✓ Playback completed")
        pygame.mixer.quit()

        # Cleanup
        temp_mp3.unlink()
        if temp_wav.exists():
            temp_wav.unlink()

        return True
    except Exception as e:
        logger.error(f"✗ Full pipeline test failed: {e}", exc_info=True)
        return False


async def main():
    """Run all diagnostics."""
    logger.info("TTS ENGINE DIAGNOSTIC REPORT")
    logger.info("=" * 50)

    results = {}

    # 1. Dependencies
    results["dependencies"] = check_dependencies()
    if not results["dependencies"]:
        logger.error("Cannot proceed without dependencies")
        return 1

    # 2. Audio converter
    converter = check_audio_converter()
    results["converter"] = converter is not None

    # 3. Pygame mixer
    results["mixer"] = check_pygame_mixer()

    # 4. Edge-TTS
    results["edge_tts"] = await test_edge_tts()

    # 5. Full pipeline (if converter available)
    if converter:
        results["full_pipeline"] = await test_full_pipeline()
    else:
        logger.warning("Skipping full pipeline test (converter missing)")
        results["full_pipeline"] = None

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("DIAGNOSTIC SUMMARY:")
    for check, passed in results.items():
        if passed is None:
            status = "⊘ SKIPPED"
        elif passed:
            status = "✓ PASS"
        else:
            status = "✗ FAIL"
        logger.info(f"  {check:20} {status}")

    # Final verdict
    critical = [results["dependencies"], results["mixer"], results["edge_tts"]]
    if all(critical):
        logger.info("\n✓ TTS system is healthy!")
        if results["converter"] and results["full_pipeline"]:
            logger.info("  Full pipeline working - audio should play in GUI")
        return 0
    else:
        logger.error("\n✗ TTS system has critical issues - see above for fixes")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
