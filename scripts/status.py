"""Check health of all locally-running Kourai agents."""

import json
import urllib.request


def check_status() -> None:
    ports = [10000, 10001, 10002, 10003, 10004, 10005]

    for port in ports:
        try:
            with urllib.request.urlopen(
                f"http://localhost:{port}/.well-known/agent-card.json", timeout=0.5
            ) as r:
                data = json.loads(r.read())
                name = data.get("name", "?")
                print(f"  OK  {name} :{port}")
        except Exception:
            print(f"  --  Port {port} not responding")


if __name__ == "__main__":
    check_status()
