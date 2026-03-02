"""Stop all Kourai Docker containers."""

import subprocess
import sys


def main():
    result = subprocess.run(
        ["docker", "compose", "--profile", "full", "down"],
    )
    if result.returncode != 0:
        print("docker compose down failed")
        sys.exit(1)
    print("All containers stopped")


if __name__ == "__main__":
    main()
