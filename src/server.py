# Zendriver MCP Server - Entry point

from src.tools import mcp


def main():
    # Run the MCP server using stdio transport.
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
