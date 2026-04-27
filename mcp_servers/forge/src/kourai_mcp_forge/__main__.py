"""Entry point — runs the forge MCP server over stdio."""

from __future__ import annotations

from kourai_mcp_forge.server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
