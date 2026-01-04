# storage tools - cookies and localStorage management
from typing import Optional

from src.tools.base import ToolBase


class StorageTools(ToolBase):
    """tools for cookies and browser storage"""

    def _register_tools(self) -> None:
        """register storage tools"""
        self._mcp.tool()(self.get_cookies)
        self._mcp.tool()(self.set_cookie)
        self._mcp.tool()(self.get_local_storage)
        self._mcp.tool()(self.set_local_storage)
        self._mcp.tool()(self.clear_storage)

    async def get_cookies(self) -> str:
        """Get all cookies for the current page."""
        cookies = await self.run_js('document.cookie')
        return cookies if cookies else "(no cookies)"

    async def set_cookie(self, name: str, value: str, domain: Optional[str] = None) -> str:
        """Set a cookie."""
        safe_name = self.escape_js_string(name)
        safe_value = self.escape_js_string(value)
        cookie_str = f"{safe_name}={safe_value}"
        if domain:
            cookie_str += f"; domain={self.escape_js_string(domain)}"
        await self.run_js(f'document.cookie = "{cookie_str}"')
        return f"Cookie set: {name}={value}"

    async def get_local_storage(self) -> str:
        """Get all localStorage items."""
        storage = await self.run_js('JSON.stringify(localStorage)')
        return storage if storage else "{}"

    async def set_local_storage(self, key: str, value: str) -> str:
        """Set a localStorage item."""
        safe_key = self.escape_js_string(key)
        safe_value = self.escape_js_string(value)
        await self.run_js(f'localStorage.setItem("{safe_key}", "{safe_value}")')
        return f"localStorage set: {key}"

    async def clear_storage(self) -> str:
        """Clear localStorage and sessionStorage."""
        await self.run_js('localStorage.clear(); sessionStorage.clear()')
        return "Cleared localStorage and sessionStorage"
