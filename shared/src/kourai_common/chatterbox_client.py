"""HTTP client for the isolated Chatterbox TTS service (M6 step 2).

The expressive engine runs out-of-process in its own torch-2.6 environment
(``services/chatterbox/``) because ``chatterbox-tts`` pins ``torch==2.6.0``,
incompatible with the shipping torch-2.11 Kokoro stack. This thin client is the
*only* thing kourai imports for Chatterbox — synthesis happens over HTTP, never
in-process. See ``services/chatterbox/server.py`` for the isolation rationale.

Failures surface as :class:`ChatterboxUnavailable` so the TTS engine can fall
back to Kokoro rather than strand a host silent.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_URL = "http://127.0.0.1:8080"
# Chatterbox generate is seconds-scale on a GPU; the timeout leaves headroom for
# the longest maiden lines + the model-warm first request.
_DEFAULT_TIMEOUT = 60.0
_HEALTH_TIMEOUT = 5.0


class ChatterboxUnavailable(RuntimeError):
    """The Chatterbox service is unreachable or returned an error response."""


class ChatterboxClient:
    """Thin async HTTP client for the isolated Chatterbox synthesis service.

    A new ``httpx.AsyncClient`` is created per call: the maidens don't synth at
    high QPS, and a per-call client sidesteps event-loop lifecycle pitfalls
    (``RealtimeTTSEngine.speak_sync`` spins up a fresh loop per utterance).
    ``transport`` is an injection seam for hermetic tests.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        resolved = base_url or os.environ.get("KOURAI_CHATTERBOX_URL", _DEFAULT_URL)
        self.base_url = resolved.rstrip("/")
        self.timeout = timeout if timeout is not None else _DEFAULT_TIMEOUT
        self._transport = transport

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=timeout, transport=self._transport)

    async def health(self) -> bool:
        """True iff the service is up and the model is loaded (200 on ``/health``)."""
        try:
            async with self._client(_HEALTH_TIMEOUT) as client:
                resp = await client.get("/health")
        except httpx.HTTPError as exc:
            logger.debug("Chatterbox health check failed: %s", exc)
            return False
        return resp.status_code == 200

    async def synthesize(
        self,
        text: str,
        *,
        voice_ref: str | None = None,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
    ) -> bytes:
        """Synthesize ``text`` to WAV bytes via the service.

        ``voice_ref`` is a *service-local* path to a reference clip for zero-shot
        cloning (omitted → the model's built-in voice). ``exaggeration`` /
        ``cfg_weight`` are the per-maiden expression knobs
        (:class:`~kourai_common.tts_backend.ChatterboxExpression`). Raises
        :class:`ChatterboxUnavailable` on any transport or HTTP error.
        """
        payload: dict[str, object] = {
            "text": text,
            "exaggeration": exaggeration,
            "cfg_weight": cfg_weight,
        }
        if voice_ref is not None:
            payload["voice_ref"] = voice_ref
        try:
            async with self._client(self.timeout) as client:
                resp = await client.post("/synthesize", json=payload)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ChatterboxUnavailable(f"Chatterbox synthesis failed: {exc}") from exc
        return resp.content
