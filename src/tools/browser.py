# browser lifecycle tools - start, stop, status
from typing import Optional

from src.tools.base import ToolBase


class BrowserTools(ToolBase):
    """tools for browser lifecycle management"""

    def _register_tools(self) -> None:
        """register browser lifecycle tools"""
        self._mcp.tool()(self.start_browser)
        self._mcp.tool()(self.stop_browser)
        self._mcp.tool()(self.get_browser_status)

    async def start_browser(
        self,
        headless: bool = False,
        proxy: Optional[str] = None,
        user_data_dir: Optional[str] = None
    ) -> str:
        """Start the browser with configuration options."""
        await self.session.start(headless=headless, proxy=proxy, user_data_dir=user_data_dir)

        # build response message
        mode = "headless" if headless else "headed"
        extras = []
        if proxy:
            extras.append(f"proxy={proxy}")
        if user_data_dir:
            extras.append(f"profile={user_data_dir}")
        extra_info = f" ({', '.join(extras)})" if extras else ""
        return f"Browser started in {mode} mode{extra_info}"

    async def stop_browser(self) -> str:
        """Stop the browser and clean up all resources."""
        await self.session.stop()
        return "Browser stopped and all resources cleaned up"

    async def get_browser_status(self) -> str:
        """Get current browser status and session info."""
        if not self.session.is_browser_started():
            return "Browser: Not started"

        # list all open tabs
        tabs = self.session.get_all_tabs()
        lines = [f"Browser: Running", f"Open tabs: {len(tabs)}"]
        for tab_id, url in tabs.items():
            lines.append(f"  - {tab_id}: {url}")
        return "\n".join(lines)
