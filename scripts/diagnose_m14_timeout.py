#!/usr/bin/env python3
"""Diagnose M14 aiohttp timeout by instrumenting TCPConnector pool state.

This script:
1. Patches aiohttp's TCPConnector to log pool state on acquire
2. Simulates concurrent LLM calls (Metis + Hephaestus)
3. Captures timeout events and pool exhaustion

Usage:
    python scripts/diagnose_m14_timeout.py

Output:
    - Console: live diagnosis
    - /tmp/m14_diagnosis.log: detailed transcript
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aiohttp.connector import TCPConnector

# Setup logging
log_handler = logging.FileHandler("/tmp/m14_diagnosis.log", "w")  # noqa: S108  # diagnostic script: fixed path documented in module docstring
log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[
        logging.StreamHandler(sys.stdout),
        log_handler,
    ],
)

log = logging.getLogger(__name__)

# Patch aiohttp to log pool state
_original_acquire = None


async def _patched_acquire(self: TCPConnector) -> Any:
    """Wrapper around TCPConnector._acquire to log pool state."""
    pool_size = len(self._pool) if hasattr(self, "_pool") else "unknown"
    waiters = len(self._waiters) if hasattr(self, "_waiters") else "unknown"

    log.debug(
        f"TCPConnector._acquire() — pool_size={pool_size}, pending_waiters={waiters}, "
        f"limit={self._limit}, limit_per_host={self._limit_per_host}"
    )

    try:
        result = await _original_acquire(self)
        log.debug("✓ Connection acquired from pool")
        return result
    except TimeoutError:
        log.error(
            f"✗ Pool acquire timeout! pool_size={pool_size}, waiters={waiters}. "
            f"This is the M14 bottleneck."
        )
        raise


async def diagnose():
    """Main diagnostic routine."""
    log.info("=" * 80)
    log.info("M14 AIOHTTP TIMEOUT DIAGNOSTIC")
    log.info("=" * 80)

    # Patch aiohttp BEFORE importing anything that uses it
    try:
        from aiohttp.connector import TCPConnector

        global _original_acquire
        _original_acquire = TCPConnector._acquire
        TCPConnector._acquire = _patched_acquire
        log.info("✓ Patched aiohttp.TCPConnector._acquire for diagnostics")
    except ImportError:
        log.error("✗ aiohttp not installed; cannot diagnose")
        return

    # Now try a scenario that triggers concurrent requests
    log.info("\nPhase 1: Baseline — Single async task")
    log.info("-" * 80)

    try:
        from kourai_common.llm import chat

        messages = [
            {"role": "system", "content": "You are a test agent."},
            {"role": "user", "content": "Say 'hello'"},
        ]

        log.info("Sending single test LLM call...")
        result = await asyncio.wait_for(
            chat("test_agent", messages, max_tokens=10),
            timeout=5.0,
        )
        log.info(f"✓ Single call succeeded: {result[:50]}...")
    except TimeoutError:
        log.error("✗ Single call timed out (pool acquire timeout)")
    except Exception as e:
        log.warning(f"Single call failed (expected if no API key): {type(e).__name__}")

    log.info("\nPhase 2: M14 Pattern — Concurrent Metis + Hephaestus")
    log.info("-" * 80)

    try:
        from agents.hephaestus.agent import determine_pipeline
        from agents.metis.agent import discuss_tradeoffs

        log.info("Spawning Metis discuss_tradeoffs as parallel task (simulating M14 dispatch)...")
        metis_task = asyncio.create_task(
            discuss_tradeoffs("implement a feature"),
            name="metis-discuss-tradeoffs",
        )

        # Small delay to let Metis start its LLM call
        await asyncio.sleep(0.05)

        log.info("Firing Hephaestus router (concurrent with Metis)...")
        routing_task = asyncio.create_task(
            determine_pipeline("implement a feature"),
            name="hephaestus-route",
        )

        # Wait for both with timeout
        log.info("Waiting for both calls to complete (30s timeout)...")
        done, pending = await asyncio.wait(
            [metis_task, routing_task],
            timeout=30,
            return_when=asyncio.ALL_COMPLETED,
        )

        log.info(f"Results: {len(done)} completed, {len(pending)} pending")

        for task in done:
            try:
                await task
                log.info(f"✓ {task.get_name()} completed")
            except TimeoutError:
                log.error(f"✗ {task.get_name()} timed out (pool exhaustion — THIS IS THE BUG)")
            except Exception as e:
                log.warning(f"✗ {task.get_name()} failed: {type(e).__name__}")

        for task in pending:
            log.error(f"✗ {task.get_name()} still pending (parallel dispatch exceeded timeout)")
            task.cancel()

    except Exception as e:
        log.error(f"Diagnostic failed: {type(e).__name__}: {e}", exc_info=True)

    log.info("\n" + "=" * 80)
    log.info("Diagnostic complete.")
    log.info("Full log saved to: /tmp/m14_diagnosis.log")
    log.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(diagnose())
