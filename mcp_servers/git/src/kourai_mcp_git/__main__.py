"""Entry point: python -m kourai_mcp_git

Agents connect via StdioServerParameters:
    StdioServerParameters(command="python", args=["-m", "kourai_mcp_git"])
"""

from kourai_mcp_git.server import mcp  # type: ignore[import-untyped]

if __name__ == "__main__":
    mcp.run()
