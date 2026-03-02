"""Start all Kourai agents locally with Jaeger for tracing."""

import os
import subprocess
import sys
import time


def start_agent(name: str) -> None:
    os.makedirs("logs", exist_ok=True)
    log_file = f"logs/{name}.log"
    with open(log_file, "w") as f:
        subprocess.Popen(
            ["uv", "run", "python", "-m", f"agents.{name}"],
            stdout=f,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )


def main() -> None:
    print("Starting Kourai Khryseai...")

    subprocess.run(["docker", "compose", "up", "-d", "jaeger", "prometheus"])

    # Specialists first, orchestrator last (needs them up)
    for name in ("mneme", "kallos", "techne", "dokimasia", "metis"):
        start_agent(name)

    time.sleep(2)
    start_agent("hephaestus")

    print("All agents launched in background")
    print("Jaeger: http://localhost:16686")
    print("Run 'make status' to check health")


if __name__ == "__main__":
    main()
