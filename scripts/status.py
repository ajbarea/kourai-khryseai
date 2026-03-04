"""Check health of all locally-running Kourai agents."""

import asyncio
import sys
import time

import httpx

PORTS = [10000, 10001, 10002, 10003, 10004, 10005]


async def check_agent(client: httpx.AsyncClient, port: int) -> str:
    """Concurrently check a single agent's health."""
    try:
        response = await client.get(
            f"http://localhost:{port}/.well-known/agent-card.json", timeout=0.5
        )
        response.raise_for_status()
        name = response.json().get("name", "?")
        return f"  OK  {name} :{port}"
    except Exception:
        return f"  --  Port {port} not responding"


async def check_all(wait: bool = False, timeout_sec: int = 30) -> None:
    """Poll all agents concurrently until healthy or timeout."""
    start_time = time.time()

    if wait:
        print("Waiting for agents to become healthy..", end="", flush=True)

    # Use a single connection pool for efficiency
    async with httpx.AsyncClient() as client:
        while True:
            # Fire all HTTP requests simultaneously
            async with asyncio.TaskGroup() as tg:
                tasks = [tg.create_task(check_agent(client, port)) for port in PORTS]

            results = [task.result() for task in tasks]
            all_ok = all("OK" in res for res in results)

            if not wait or all_ok or (time.time() - start_time) > timeout_sec:
                if wait:
                    print()  # newline after waiting indicator
                for res in results:
                    print(res)

                if wait and not all_ok:
                    print("\nWarning: Some agents failed to start in time.", file=sys.stderr)
                    sys.exit(1)
                break

            if wait:
                print(".", end="", flush=True)
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    wait_mode = "--wait" in sys.argv
    try:
        asyncio.run(check_all(wait=wait_mode))
    except KeyboardInterrupt:
        sys.exit(1)
