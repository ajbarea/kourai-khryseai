"""Stop all locally-running Kourai agent processes."""

import argparse

import psutil


def stop_agents(total: bool = False) -> None:
    stopped = 0
    for proc in psutil.process_iter(["cmdline"]):
        try:
            cmdline = proc.info["cmdline"]
            if not cmdline or len(cmdline) < 3:
                continue
            # Match: uv run python -m agents.<name> OR python -m agents.<name>
            joined = " ".join(cmdline)
            if "-m" in joined and "agents." in joined:
                proc.terminate()
                stopped += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if stopped:
        print(f"Stopped {stopped} agent process(es)")
    else:
        print("No running agents found")

    if total:
        print("Total system shutdown complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--total", action="store_true")
    args = parser.parse_args()
    stop_agents(total=args.total)
