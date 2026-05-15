"""M14 Parallel Dispatch Timeout Reproduction.

Test case: Send "hi dokimasia, are you there?" to Hephaestus,
which triggers concurrent Metis discuss_tradeoffs + Hephaestus routing
calls. Both hit Anthropic API via LiteLLM + aiohttp.

Expected: Capture aiohttp connection pool timeout (if it occurs).
"""

from __future__ import annotations

import asyncio
import logging
import os

# Enable aiohttp debug logging BEFORE importing anything that uses it
logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"detailed": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "stream": "ext://sys.stdout",
        },
        "aiohttp_file": {
            "class": "logging.FileHandler",
            "filename": "/tmp/aiohttp_debug.log",  # noqa: S108  # CI runner /tmp is isolated; diagnostic path is intentional
            "level": "DEBUG",
            "formatter": "detailed",
        },
    },
    "loggers": {
        "aiohttp": {
            "level": "DEBUG",
            "handlers": ["console", "aiohttp_file"],
        },
        "aiohttp.connector": {
            "level": "DEBUG",
            "handlers": ["console", "aiohttp_file"],
        },
        "asyncio": {
            "level": "DEBUG",
            "handlers": ["console", "aiohttp_file"],
        },
    },
}

import logging.config

logging.config.dictConfig(logging_config)


# Now import the agent module

log = logging.getLogger(__name__)


async def test_m14_parallel_dispatch_timeout():
    """Reproduce the M14 timeout by sending a message that triggers parallel dispatch."""
    log.info("=" * 80)
    log.info("M14 PARALLEL DISPATCH TIMEOUT REPRODUCTION TEST")
    log.info("=" * 80)
    log.info("Scenario: User sends 'hi dokimasia, are you there?'")
    log.info("Expected: Metis discuss_tradeoffs + Hephaestus routing run in parallel")
    log.info("Goal: Capture aiohttp connection pool timeout (if it occurs)")
    log.info("=" * 80)

    # Set environment for clean testing
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-if-not-set")
    os.environ.setdefault("KOURAI_LOG_LEVEL", "DEBUG")

    # Import after env setup
    from agents.metis.agent import discuss_tradeoffs

    log.info("\nPhase 1: Testing single Hephaestus routing call (baseline)")
    log.info("-" * 80)

    try:
        # Single routing call — should work cleanly
        from agents.hephaestus.agent import determine_pipeline

        result1 = await asyncio.wait_for(
            determine_pipeline("hi dokimasia, are you there?"), timeout=30
        )
        log.info(f"Single routing result: {result1[:100]}...")
    except Exception as e:
        log.warning(f"Single routing failed: {type(e).__name__}: {e}")

    log.info("\nPhase 2: Testing parallel Metis + Hephaestus (M14 pattern)")
    log.info("-" * 80)

    try:
        metis_task = asyncio.create_task(
            discuss_tradeoffs("hi dokimasia, are you there?"),
            name="metis-discuss-tradeoffs",
        )
        log.info("Spawned Metis discuss_tradeoffs as parallel task")

        # Give Metis a moment to start, then fire Hephaestus router
        await asyncio.sleep(0.1)

        routing_task = asyncio.create_task(
            determine_pipeline("hi dokimasia, are you there?"),
            name="hephaestus-route",
        )
        log.info("Fired Hephaestus routing call (concurrent with Metis)")

        # Wait for both with timeout
        done, pending = await asyncio.wait(
            [metis_task, routing_task],
            timeout=35,
            return_when=asyncio.ALL_COMPLETED,
        )
        log.info(f"Completed: {len(done)} tasks, Pending: {len(pending)} tasks")

        for task in done:
            try:
                _ = await task
                log.info(f"✓ {task.get_name()} succeeded")
            except Exception as e:
                log.error(f"✗ {task.get_name()} failed: {type(e).__name__}: {e}")

        for task in pending:
            log.error(f"✗ {task.get_name()} timed out (still pending)")
            task.cancel()

    except Exception as e:
        log.error(f"Parallel test failed: {type(e).__name__}: {e}", exc_info=True)

    log.info("\n" + "=" * 80)
    log.info("Test complete. Check /tmp/aiohttp_debug.log for transport details.")
    log.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_m14_parallel_dispatch_timeout())
