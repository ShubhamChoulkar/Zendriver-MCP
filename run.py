# Runner script for Zendriver MCP server
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.tools import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
