"""Start all Kourai agents in Docker with full profile."""

import subprocess
import sys


def main():
    result = subprocess.run(
        ["docker", "compose", "--profile", "full", "up", "-d", "--build"],
    )
    if result.returncode != 0:
        print("docker compose up failed")
        sys.exit(1)
    print("All agents running in Docker")
    print("Jaeger: http://localhost:16686")


if __name__ == "__main__":
    main()
