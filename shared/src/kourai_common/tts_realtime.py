"""RealtimeTTS-backed TTS engine — bundles Kokoro synth + PyAudio playback.

Replaces the pygame.mixer-based TTS path on the CLI and GUI hosts and the
hand-rolled KokoroBackend/EdgeTTSBackend path on the VN bridge. pygame.mixer's
documented inability to reliably resample 24 kHz mono → 44.1 kHz stereo
produced the "VHS rewind" chipmunk symptom; RealtimeTTS routes Kokoro's
native 24 kHz mono through PyAudio with no resample step in the path.

Two public surfaces:

- ``speak`` / ``speak_sync`` for CLI + GUI — synth + PyAudio playback bundled.
- ``synthesize_to_wav`` for ``agents/vn_bridge/`` — synth-only path that
  drives ``TextToAudioStream`` with ``muted=True`` and an ``on_audio_chunk``
  collector, then wraps the int16 PCM in one WAV header sized from
  ``KokoroEngine.get_stream_info()``.

Future ElevenLabs swap (M6) becomes a one-line engine change inside
``__init__``.
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
import wave
from typing import TYPE_CHECKING

# Module-level bindings (aliased with leading underscore) so tests can
# monkeypatch them without instantiating PyAudio. RealtimeTTS is a hard
# dep in hosts/gui/pyproject.toml; importing it pulls in pyaudio, which
# requires portaudio19-dev on Linux (CI installs it via ed4d560).
import pyaudio
from RealtimeTTS import KokoroEngine as _KokoroEngine, TextToAudioStream as _TextToAudioStream

from kourai_common.audio_env import silence_alsa_lib_errors, silence_audio_init_noise
from kourai_common.tts_backend import (
    AGENT_VOICE_MAP,
    TTSVoiceConfig,
    get_voice_for_agent,
)

# Module-load side effect: kill libasound's stderr cascade before
# `_TextToAudioStream(...)` enumerates ALSA in `__init__` below.
silence_alsa_lib_errors()

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# Re-exports for parity with hosts.gui.tts_engine
VoiceConfig = TTSVoiceConfig
VOICE_ROSTER = {v.voice_id: v for v in AGENT_VOICE_MAP.values()}
AGENT_VOICES = {agent: cfg.voice_id for agent, cfg in AGENT_VOICE_MAP.items()}


class _DropPhonemizerWordsCountMismatch(logging.Filter):
    """Surgical filter for the 'words count mismatch' espeak spam.

    phonemizer's espeak backend logs ``words count mismatch on N% of the
    lines (X/Y)`` at WARNING from ``_resume()`` after every batch, even
    when ``words_mismatch='ignore'`` is set (which is the default).
    Upstream confirms it's benign — espeak occasionally joins or drops a
    word and the audio is still correct. Filtering only this message
    pattern keeps any other phonemizer warnings audible.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return "words count mismatch" not in record.getMessage()


_phonemizer_filter_installed = False


def _install_phonemizer_word_count_filter() -> None:
    """Idempotently attach the words-count-mismatch filter to phonemizer's logger."""
    global _phonemizer_filter_installed
    if _phonemizer_filter_installed:
        return
    logging.getLogger("phonemizer").addFilter(_DropPhonemizerWordsCountMismatch())
    _phonemizer_filter_installed = True


def _pcm_to_wav(pcm: bytes, *, channels: int, sample_rate: int, sample_width: int) -> bytes:
    """Wrap raw signed PCM bytes in a canonical WAV header."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buf.getvalue()


class RealtimeTTSEngine:
    """TTS engine wrapping RealtimeTTS's KokoroEngine + TextToAudioStream.

    PyAudio-backed playback at native 24 kHz mono — no pygame mixer in
    the path, so the resample "VHS rewind" failure mode is gone by
    construction. Mirrors ``TTSEngine``'s ABI for drop-in replacement.
    """

    def __init__(
        self,
        master_volume: float = 0.8,
        enable_effects: bool = True,
        muted: bool = False,
        on_word: Callable[[object], None] | None = None,
    ):
        # Install before engine init so misaki's first phonemize() call
        # (which can happen during KokoroEngine warmup) is already filtered.
        _install_phonemizer_word_count_filter()
        self._engine = _KokoroEngine(voice="af_heart", default_speed=1.0, debug=False)
        # PyAudio probes JACK after ALSA inside `_TextToAudioStream`;
        # wrap only that call so torch / HF Hub warnings stay visible.
        with silence_audio_init_noise():
            self._stream = _TextToAudioStream(
                engine=self._engine,
                on_word=on_word,
                muted=muted,
                level=logging.WARNING,
            )

        self.master_volume = max(0.0, min(1.0, master_volume))
        self.enable_effects = enable_effects
        self.is_playing = False
        self._on_complete: Callable[[], None] | None = None

        self._stream.set_volume(self._effective_volume())

        # Eat the Kokoro cold-start window upfront: pipelines per
        # language (#23), then voice tensors per agent (M20 sub-task 1).
        self._prewarm_agent_languages()
        self._prewarm_agent_voices()

        logger.info(
            "RealtimeTTSEngine initialized: voice=af_heart, volume=%s, effects=%s",
            self.master_volume,
            self.enable_effects,
        )

    def _prewarm_agent_languages(self) -> None:
        """Build a KPipeline for every unique ``AGENT_VOICE_MAP`` lang_code.

        Failures are non-fatal — the lazy path still works if pre-warm misses.
        """
        t_start = time.monotonic()
        seen: set[str] = set()
        loaded: list[str] = []
        for cfg in AGENT_VOICE_MAP.values():
            lang_code = getattr(cfg, "lang_code", "a")
            if lang_code in seen:
                continue
            seen.add(lang_code)
            try:
                self._engine._get_pipeline(lang_code)
                loaded.append(lang_code)
            except Exception as exc:
                logger.debug(
                    "Kokoro pre-warm skipped for lang_code=%s (%s: %s)",
                    lang_code,
                    type(exc).__name__,
                    exc,
                )
        logger.info(
            "Kokoro language pre-warm: %d/%d langs (%s) elapsed=%.2fs",
            len(loaded),
            len(seen),
            ",".join(sorted(loaded)) or "none",
            time.monotonic() - t_start,
        )

    def _prewarm_agent_voices(self) -> None:
        """Materialize each agent's voice tensor (.pt) into KPipeline's voice cache.

        Failures are non-fatal — single-voice failure falls back to the lazy path.
        """
        t_start = time.monotonic()
        loaded: list[str] = []
        for cfg in AGENT_VOICE_MAP.values():
            lang_code = getattr(cfg, "lang_code", "a")
            try:
                pipeline = self._engine._get_pipeline(lang_code)
                pipeline.load_single_voice(cfg.voice_id)
                loaded.append(cfg.voice_id)
            except Exception as exc:
                logger.debug(
                    "Kokoro voice pre-warm skipped for voice=%s lang=%s (%s: %s)",
                    cfg.voice_id,
                    lang_code,
                    type(exc).__name__,
                    exc,
                )
        logger.info(
            "Kokoro voice pre-warm: %d/%d voices elapsed=%.2fs",
            len(loaded),
            len(AGENT_VOICE_MAP),
            time.monotonic() - t_start,
        )

    def _effective_volume(self) -> float:
        return self.master_volume * (0.85 if self.enable_effects else 1.0)

    def set_master_volume(self, volume: float) -> None:
        """Set master volume (0.0 to 1.0)."""
        self.master_volume = max(0.0, min(1.0, volume))
        self._stream.set_volume(self._effective_volume())
        logger.debug("Master volume set to %s", self.master_volume)

    def set_on_complete(self, callback: Callable[[], None]) -> None:
        """Set callback to fire when playback completes."""
        self._on_complete = callback

    async def speak(
        self,
        text: str,
        agent_name: str | None = None,
        voice_key: str | None = None,
        speed: float | None = None,
        pitch: float | None = None,
    ) -> None:
        """Generate and play speech asynchronously.

        ``pitch`` is accepted for ABI parity with ``TTSEngine.speak`` but
        ignored — KokoroEngine has no pitch control (the legacy
        ``KokoroBackend`` also dropped it for the same reason).
        """
        if not text.strip():
            logger.debug("Empty text, skipping TTS")
            return

        # Resolve voice
        if voice_key is not None:
            voice_cfg = VOICE_ROSTER.get(voice_key, get_voice_for_agent(None))
        else:
            voice_cfg = get_voice_for_agent(agent_name)

        effective_speed = speed if speed is not None else voice_cfg.speed

        t_start = time.monotonic()
        try:
            logger.info(
                "TTS: starting RealtimeTTS speech — agent=%s, voice=%s, speed=%.2f, text=%r",
                agent_name,
                voice_cfg.voice_id,
                effective_speed,
                text,
            )

            self._engine.set_voice(voice_cfg.voice_id)
            self._engine.set_speed(effective_speed)

            self.is_playing = True
            self._stream.feed(text)

            # Bridge RealtimeTTS's blocking play() into the async loop.
            # play() runs synthesis + playback to completion on a worker
            # thread, returning when the audio stream stops.
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._stream.play)

            logger.info(
                "TTS: playback complete agent=%s voice=%s elapsed=%.2fs chars=%d",
                agent_name,
                voice_cfg.voice_id,
                time.monotonic() - t_start,
                len(text),
            )
        except Exception as e:
            # TTS is non-critical; keep the console line terse.
            logger.warning("TTS playback skipped (%s: %s)", type(e).__name__, e)
            logger.debug("TTS playback error detail", exc_info=True)
        finally:
            self.is_playing = False
            if self._on_complete:
                self._on_complete()

    def speak_sync(
        self,
        text: str,
        agent_name: str | None = None,
        voice_key: str | None = None,
        speed: float | None = None,
        pitch: float | None = None,
    ) -> None:
        """Synchronous wrapper for speak (blocks until complete)."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.speak(
                    text,
                    agent_name=agent_name,
                    voice_key=voice_key,
                    speed=speed,
                    pitch=pitch,
                )
            )
        finally:
            loop.close()

    async def synthesize_to_wav(
        self,
        text: str,
        agent_name: str | None = None,
        voice_key: str | None = None,
        speed: float | None = None,
    ) -> bytes:
        """Generate speech as a self-contained WAV without playback.

        Drives ``TextToAudioStream`` with ``muted=True`` and an
        ``on_audio_chunk`` collector — RealtimeTTS's documented bytes-only
        path — then wraps the int16 PCM in one WAV header sized from
        ``KokoroEngine.get_stream_info()``. Used by ``agents/vn_bridge/``
        which feeds WAV bytes into Ren'Py's audio system rather than
        playing them itself.
        """
        if not text.strip():
            return b""

        # Voice resolution mirrors speak() so vn_bridge and the CLI/GUI
        # hosts dispatch through the same precedence rules.
        if voice_key is not None:
            voice_cfg = VOICE_ROSTER.get(voice_key, get_voice_for_agent(None))
        else:
            voice_cfg = get_voice_for_agent(agent_name)
        effective_speed = speed if speed is not None else voice_cfg.speed

        chunks: list[bytes] = []
        t_start = time.monotonic()

        self._engine.set_voice(voice_cfg.voice_id)
        self._engine.set_speed(effective_speed)
        self._stream.feed(text)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._stream.play(muted=True, on_audio_chunk=chunks.append),
        )

        synth_elapsed = time.monotonic() - t_start

        if not chunks:
            logger.info(
                "TTS: synthesize_to_wav produced no audio agent=%s voice=%s elapsed=%.2fs",
                agent_name,
                voice_cfg.voice_id,
                synth_elapsed,
            )
            return b""

        fmt, channels, sample_rate = self._engine.get_stream_info()
        wav = _pcm_to_wav(
            b"".join(chunks),
            channels=channels,
            sample_rate=sample_rate,
            sample_width=pyaudio.get_sample_size(fmt),
        )
        logger.info(
            "TTS: synthesize_to_wav agent=%s voice=%s elapsed=%.2fs chars=%d bytes=%d",
            agent_name,
            voice_cfg.voice_id,
            synth_elapsed,
            len(text),
            len(wav),
        )
        return wav

    def stop(self) -> None:
        """Stop current playback gracefully."""
        try:
            self._stream.stop()
        except Exception as e:
            logger.debug("RealtimeTTS stop ignored (%s: %s)", type(e).__name__, e)
        self.is_playing = False

    def cleanup(self) -> None:
        """Stop playback and shut the KokoroEngine down."""
        self.stop()
        try:
            self._engine.shutdown()
        except Exception as e:
            logger.debug("KokoroEngine shutdown ignored (%s: %s)", type(e).__name__, e)
        logger.debug("RealtimeTTSEngine cleanup complete")
