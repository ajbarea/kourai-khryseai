"""Isolated Chatterbox TTS HTTP service.

Runs in its OWN torch-2.6 environment (see this directory's ``pyproject.toml``
and ``README.md``), deliberately *outside* the kourai uv workspace:
``chatterbox-tts`` hard-pins ``torch==2.6.0``, which would downgrade the
shipping torch-2.11 Kokoro stack if it shared the main resolution.
``research(2026-05)``: the uv docs state workspaces are "not suited for cases
in which members have conflicting requirements" and recommend a separate
project — so kourai talks to this over HTTP (``kourai_common.chatterbox_client``)
and never imports ``chatterbox`` in-process.

One model, loaded once on the GPU at startup; ``POST /synthesize`` returns a
WAV. ``research(2026-05)``: devnen/Chatterbox-TTS-Server is the reference shape;
this is the minimal slice kourai needs (no WebUI / audiobook chunking).
"""

from __future__ import annotations

import io
import logging
import os
import threading
import wave
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import torch
from chatterbox.tts import ChatterboxTTS
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger("chatterbox_service")

_DEVICE = os.environ.get("CHATTERBOX_DEVICE", "cuda")

# generate() serializes on the single GPU; the lock keeps concurrent requests
# from interleaving CUDA graphs on the one model (and from racing OOM).
_gen_lock = threading.Lock()


class SynthesizeRequest(BaseModel):
    """One utterance. Ranges mirror ``kourai_common.tts_backend.ChatterboxExpression``."""

    text: str = Field(min_length=1, max_length=2000)
    voice_ref: str | None = None  # server-local path to a reference clip (zero-shot clone)
    exaggeration: float = Field(default=0.5, ge=0.25, le=2.0)
    cfg_weight: float = Field(default=0.5, ge=0.0, le=1.0)


class _ModelHolder:
    model: ChatterboxTTS | None = None


_holder = _ModelHolder()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Chatterbox's sampling loop draws a per-step tqdm bar to stderr; disable it
    # so the service log stays one line per request, not a thousand.
    os.environ["TQDM_DISABLE"] = "1"
    logger.info("loading ChatterboxTTS on %s ...", _DEVICE)
    _holder.model = await run_in_threadpool(ChatterboxTTS.from_pretrained, device=_DEVICE)
    logger.info("model ready (sr=%d, device=%s)", _holder.model.sr, _DEVICE)
    yield
    _holder.model = None


app = FastAPI(title="kourai chatterbox service", lifespan=lifespan)


def _wav_bytes(wav: torch.Tensor, sample_rate: int) -> bytes:
    """Encode a float ``[-1, 1]`` mono tensor as 16-bit PCM WAV (stdlib only)."""
    samples = wav.detach().cpu().squeeze().clamp(-1.0, 1.0)
    pcm = (samples * 32767.0).to(torch.int16).numpy().tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes(pcm)
    return buf.getvalue()


@app.get("/health")
async def health() -> JSONResponse:
    # 503 while the model loads (readiness-probe semantics) so callers — and the
    # kourai client's health() — can treat 200 as "ready to synthesize".
    model = _holder.model
    ready = model is not None
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ok" if ready else "loading",
            "device": _DEVICE,
            "sample_rate": model.sr if ready else None,
        },
    )


@app.post("/synthesize")
async def synthesize(req: SynthesizeRequest) -> Response:
    model = _holder.model
    if model is None:
        raise HTTPException(status_code=503, detail="model still loading")

    def _run() -> bytes:
        # The voice_ref stat + generate both run here in the threadpool, so the
        # filesystem touch isn't blocking the event loop (ruff ASYNC240).
        audio_prompt_path: str | None = None
        if req.voice_ref:
            ref = Path(req.voice_ref)
            if not ref.is_file():
                raise HTTPException(status_code=400, detail=f"voice_ref not found: {req.voice_ref}")
            audio_prompt_path = str(ref)
        with _gen_lock:
            wav = model.generate(
                req.text,
                audio_prompt_path=audio_prompt_path,
                exaggeration=req.exaggeration,
                cfg_weight=req.cfg_weight,
            )
        return _wav_bytes(wav, model.sr)

    audio = await run_in_threadpool(_run)
    return Response(content=audio, media_type="audio/wav")


def main() -> None:
    import uvicorn

    host = os.environ.get("CHATTERBOX_HOST", "127.0.0.1")
    port = int(os.environ.get("CHATTERBOX_PORT", "8080"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
