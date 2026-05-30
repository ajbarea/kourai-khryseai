# Chatterbox TTS service

The expressive voice engine for kourai's maidens (M6), run **out-of-process** in
its own environment and reached over HTTP by
[`kourai_common.chatterbox_client`](../../shared/src/kourai_common/chatterbox_client.py).

## Why it's isolated

`chatterbox-tts` hard-pins `torch==2.6.0`. The kourai workspace ships
`torch==2.11` (the Kokoro stack). Those can't coexist in one resolution, and the
[uv docs](https://docs.astral.sh/uv/concepts/projects/workspaces/) say workspaces
are "not suited for cases in which members have conflicting requirements" —
recommending a separate project instead. So this directory is an **independent uv
project**, excluded from the root workspace (`exclude = ["services/*"]`), with its
own lockfile and venv. kourai never imports `chatterbox` in-process.

## Setup & run (GPU)

```bash
cd services/chatterbox
uv sync                       # own torch-2.6 venv; never touches the main lock
uv run python server.py       # loads the model once, serves on 127.0.0.1:8080
```

The model (~13 s cold load) downloads from the HF Hub on first run and is cached.
A CUDA GPU is expected; set `CHATTERBOX_DEVICE=cpu` to force CPU (much slower).

| env var | default | meaning |
| --- | --- | --- |
| `CHATTERBOX_HOST` | `127.0.0.1` | bind host (local-only by default) |
| `CHATTERBOX_PORT` | `8080` | bind port |
| `CHATTERBOX_DEVICE` | `cuda` | torch device for the model |
| `KOURAI_CHATTERBOX_URL` | `http://127.0.0.1:8080` | where the **client** looks for this service |

## Endpoints

- `GET /health` → `200 {"status":"ok",...}` once the model is loaded; `503` while
  loading (readiness-probe semantics).
- `POST /synthesize` `{text, voice_ref?, exaggeration?, cfg_weight?}` →
  `audio/wav` (mono 24 kHz 16-bit). `voice_ref` is a **service-local** path to a
  reference clip for zero-shot cloning; omit it for the built-in voice.
  `exaggeration` ∈ [0.25, 2.0], `cfg_weight` ∈ [0.0, 1.0] (422 if out of range).

## perth watermark note

Chatterbox watermarks output via Resemble's `perth`, which imports `pkg_resources`
— removed in setuptools 81+. The pin `setuptools<81` (see `pyproject.toml`) keeps
the **real** `PerthImplicitWatermarker` working rather than falling back to a
no-op dummy. AI-generated voices ship watermarked by default; that's intentional.
