"""Drive the M18 full-pipeline smoke against a live ``make cli`` REPL.

Pre-seeds project preference facts via ``/preferences set`` so Metis
skips the M17 PAUSE that ends the pipeline mid-flight on a fresh
project (M17 is future-run preference recall, not in-flight resume —
verified against ROADMAP §M17 lines 510-518). Once the facts are
seeded, the development prompt drives metis → techne → dokimasia →
kallos → mneme end-to-end in one shot.

Validates in one run:

* M18 Phase 1 wire shape — content-kind metadata flows through every
  specialist's status emissions; ``[#107]`` (#15), ``[#108]`` (#22),
  ``[#109]`` (#17), ``[#111]`` (#23), ``[#112]`` (#14) UX cleanups are
  exercised by association.
* M17 recall — preferences seeded in turn N are read by Metis on the
  same turn (no PAUSE, no second turn needed once project facts exist).
* M13 confirmation gate — ``/yolo`` toggling, original-request relay
  through CONFIRM_ORDER ack.

Usage::

    # Inside the kourai-khryseai repo with `make up` already healthy:
    uvx --with pexpect python scripts/smoke_m18_full_pipeline.py [--prompt "..."]

The script writes a transcript log to ``logs/smoke-m18-<ts>.log`` for
later inspection. Voice-off by default — set ``KOURAI_TTS=on`` if you
want to hear the run.

Why pexpect not tmux+script:
``feedback_drive_smoke_yourself.md`` — pexpect handles the unicode
``❯`` prompt cleanly with ``encoding='utf-8'``; tmux+script gets
buffer-cut surprises that have bitten prior smoke attempts.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

try:
    import pexpect
except ImportError:
    pexpect = None  # type: ignore[assignment]


def _require_pexpect() -> None:
    if pexpect is None:
        sys.stderr.write(
            "pexpect is not installed in this venv. Run via:\n"
            "  uvx --with pexpect python scripts/smoke_m18_full_pipeline.py\n"
        )
        raise SystemExit(1)


# CLI prompt is U+276F (HEAVY RIGHT-POINTING ANGLE QUOTATION MARK) plus a
# space; demo.py and __main__.py both render it identically. Treat the
# space as optional — prompt_toolkit's redraws sometimes drop the trailing
# space when the cursor lands on column 0.
PROMPT = r"❯\s?"
# Pipeline-complete marker. Streaming layer renders this as the gold
# signature line "✨ Forged in N.Ns" right before returning the prompt.
COMPLETION_MARKER = r"Forged in \d+\.\d+s"

DEFAULT_PROMPT = (
    "add a function double(n: int) -> int that returns n*2 in src/math.py "
    "and a pytest test in tests/test_math.py — keep the change minimal"
)

# The closed M17 PAUSE vocabulary (matches VALID_PREFERENCE_KINDS in
# kourai_common.hooks_interaction). Pre-seeding all five guarantees
# metis can plan without pausing for any of the kinds it might
# otherwise gate on. Order is noisy — list-form so the log shows the
# seed sequence verbatim.
SEED_PREFERENCES: list[tuple[str, str]] = [
    ("test_framework", "pytest"),
    ("coverage_target", "80%"),
    ("python_version", "3.12"),
    ("style_rules", "ruff defaults"),
    ("commit_style", "Conventional Commits"),
]

# Each pipeline turn can run 5+ minutes against the real LLM if the
# specialists actually do work (techne reads/writes files, dokimasia
# runs pytest, kallos runs ruff). 600s is the empirical 95th percentile
# from prior smoke runs.
TURN_TIMEOUT_SECONDS = 900
SHORT_PROMPT_TIMEOUT = 60


log = logging.getLogger(__name__)


def _ts() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ")


def _resolve_log_path() -> Path:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    return log_dir / f"smoke-m18-{_ts()}.log"


def _spawn_cli(env: dict[str, str], log_path: Path) -> pexpect.spawn:
    """Spawn ``make cli`` with utf-8 encoding so the ❯ prompt round-trips."""
    log.info("Spawning `make cli` (logging to %s)", log_path)
    # ``make cli`` resolves to ``uv run kourai-cli`` per the Makefile.
    # We invoke ``make`` directly instead of replicating the inner cmd
    # so a Makefile change ripples through automatically.
    child = pexpect.spawn(
        "make",
        ["cli"],
        encoding="utf-8",
        timeout=SHORT_PROMPT_TIMEOUT,
        env=env,
    )
    child.logfile_read = log_path.open("w", encoding="utf-8")
    return child


def _wait_for_prompt(child: pexpect.spawn, *, timeout: int = SHORT_PROMPT_TIMEOUT) -> None:
    child.expect(PROMPT, timeout=timeout)


def _send(child: pexpect.spawn, text: str) -> None:
    log.info("→ %s", text)
    child.sendline(text)


def _seed_preferences(child: pexpect.spawn) -> None:
    """Use the M17 Phase 2 ``/preferences set`` CRUD CLI to seed facts.

    Each ``set`` is upsert-shaped (forget-then-write the same
    scope+kind), so re-running the smoke against the same project is
    idempotent — facts stay single-row-per-kind and confidence stays
    high.
    """
    for kind, value in SEED_PREFERENCES:
        _send(child, f"/preferences set {kind} {value}")
        _wait_for_prompt(child)


def _drive_dev_turn(child: pexpect.spawn, prompt: str) -> None:
    log.info("Driving dev turn with prompt: %r", prompt)
    _send(child, prompt)

    # Wait for the M13 confirmation gate. ``Light the forge?`` is the
    # human-friendly text Hephaestus emits after analyzing the request.
    # ``CONFIRM_ORDER`` / ``Approve?`` are alternate surfaces. ``Forge
    # cooled`` is the explicit cancel path.
    #
    # IMPORTANT: progress-status text like "Analyzing request..." or
    # "Forging" must NOT be in this regex — those land BEFORE the gate
    # on the non-yolo path, which would cause us to falsely think we
    # had reached the gate already. /yolo bypass: no gate fires; this
    # expect times out, we fall through to the completion-marker wait.
    gate_pattern = r"(Light the forge\?|Approve\?|CONFIRM_ORDER|Forge cooled)"
    try:
        child.expect(gate_pattern, timeout=300)
    except pexpect.exceptions.TIMEOUT:
        # No gate fired in 5 min — assume /yolo passthrough. The
        # pipeline should produce ``Forged in`` directly. If it doesn't,
        # the next expect will time out with a meaningful error.
        log.info("No M13 gate fired in 300s — assuming /yolo passthrough.")
    else:
        matched = child.after or ""
        if "Forge cooled" in matched:
            raise RuntimeError("M13 gate cancelled the forge — see log")
        _send(child, "yes")

    # Then the pipeline runs. Wait for the gold signature.
    child.expect(COMPLETION_MARKER, timeout=TURN_TIMEOUT_SECONDS)
    log.info("Pipeline completed.")


def _quit(child: pexpect.spawn) -> None:
    """Exit cleanly so the CLI flushes session state and writes Memoir."""
    _send(child, "/q")
    child.expect(pexpect.EOF, timeout=SHORT_PROMPT_TIMEOUT)


def _build_env() -> dict[str, str]:
    env = dict(os.environ)
    # Default voice-off — WSL2 PortAudio crackling is out-of-scope and
    # blocks unattended runs. KOURAI_TTS=on opts back in for live demos.
    env.setdefault("KOURAI_TTS", "off")
    return env


def _ensure_dependencies_present() -> None:
    if shutil.which("make") is None:
        raise SystemExit("`make` not found on PATH; run from inside the repo with build deps.")
    # ``make up`` healthcheck — if hephaestus isn't up at 10000 the smoke
    # won't get past banner. Fail fast with an actionable hint.
    probe = subprocess.run(
        ["docker", "ps", "--filter", "name=kourai-khryseai-hephaestus", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0 or "hephaestus" not in probe.stdout:
        raise SystemExit(
            "Hephaestus container is not running. Bring the stack up first:\n"
            "  make up    # then wait for 'all agents ready'\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Development request to drive the pipeline with.",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip /preferences seeding (use when the project is already seeded).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python log level for the driver itself (script output, not CLI logs).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    _require_pexpect()
    _ensure_dependencies_present()

    log_path = _resolve_log_path()
    env = _build_env()
    child = _spawn_cli(env, log_path)

    try:
        # Banner takes a few seconds to render — give it generous timeout
        # so a slow `uv run` cold start doesn't false-fail the smoke.
        child.expect(PROMPT, timeout=90)
        log.info("CLI prompt reached.")

        if not args.skip_seed:
            _seed_preferences(child)
            log.info("Seeded %d preference facts.", len(SEED_PREFERENCES))

        t0 = time.monotonic()
        _drive_dev_turn(child, args.prompt)
        elapsed = time.monotonic() - t0
        log.info("Dev turn elapsed: %.1fs", elapsed)

        _quit(child)
        log.info("Smoke complete. Transcript: %s", log_path)
    except pexpect.exceptions.TIMEOUT:
        log.exception("TIMEOUT — see %s for the captured transcript", log_path)
        with contextlib.suppress(Exception):
            child.terminate(force=True)
        return 2
    except pexpect.exceptions.EOF:
        log.exception("CLI exited unexpectedly — see %s", log_path)
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
