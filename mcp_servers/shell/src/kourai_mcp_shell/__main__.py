"""Entry point: python -m kourai_mcp_shell

Agents connect via StdioServerParameters:
    StdioServerParameters(command="python", args=["-m", "kourai_mcp_shell"])
"""

from kourai_mcp_shell.server import mcp  # type: ignore[import-untyped]

if __name__ == "__main__":
    mcp.run()
