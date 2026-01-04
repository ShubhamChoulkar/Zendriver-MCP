# tab management tools - new tab, list, switch, close
from typing import Optional

from src.tools.base import ToolBase


class TabTools(ToolBase):
    """tools for multi-tab management"""

    def _register_tools(self) -> None:
        """register tab management tools"""
        self._mcp.tool()(self.new_tab)
        self._mcp.tool()(self.list_tabs)
        self._mcp.tool()(self.switch_tab)
        self._mcp.tool()(self.close_tab)

    async def new_tab(self, url: Optional[str] = None) -> str:
        """Open a new browser tab."""
        tab_id, tab = await self.session.create_tab(url)
        self.session.page = tab
        return f"Opened new tab: {tab_id}" + (f" at {url}" if url else "")

    async def list_tabs(self) -> str:
        """List all open tabs."""
        tabs = self.session.get_all_tabs()
        if not tabs:
            return "No tabs open"
        lines = [f"Open tabs ({len(tabs)}):"]
        for tab_id, url in tabs.items():
            lines.append(f"  - {tab_id}: {url}")
        return "\n".join(lines)

    async def switch_tab(self, tab_id: str) -> str:
        """Switch to a specific tab."""
        await self.session.switch_tab(tab_id)
        return f"Switched to {tab_id}"

    async def close_tab(self, tab_id: str) -> str:
        """Close a specific tab."""
        await self.session.close_tab(tab_id)
        return f"Closed tab: {tab_id}"
