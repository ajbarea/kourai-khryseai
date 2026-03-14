"""Entry point: python -m kourai_mcp_filesystem

Agents connect via StdioServerParameters:
    StdioServerParameters(command="python", args=["-m", "kourai_mcp_filesystem"])
"""

from kourai_mcp_filesystem.server import mcp  # type: ignore[import-untyped]

if __name__ == "__main__":
    mcp.run()
