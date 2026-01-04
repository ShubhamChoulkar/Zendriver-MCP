# base class for all tool modules
import time
from abc import ABC
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from src.session import BrowserSession
from src.errors import ElementNotFoundError


class ToolBase(ABC):
    """base class providing shared functionality for all tool modules"""

    def __init__(self, mcp: FastMCP):
        self._mcp = mcp
        self._session = BrowserSession.get_instance()
        self._register_tools()

    def _register_tools(self) -> None:
        """override in subclasses to register tools with mcp"""
        pass

    @property
    def session(self) -> BrowserSession:
        """get browser session instance"""
        return self._session

    @property
    def mcp(self) -> FastMCP:
        """get mcp server instance"""
        return self._mcp

    @staticmethod
    def escape_js_string(s: str) -> str:
        """escape special characters for safe JavaScript string interpolation"""
        return (s.replace("\\", "\\\\")
                 .replace('"', '\\"')
                 .replace("'", "\\'")
                 .replace("\n", "\\n")
                 .replace("\r", "\\r"))

    async def get_element(self, selector: str):
        """get element by selector, raise error if not found"""
        elem = await self._session.page.select(selector)
        if elem is None:
            raise ElementNotFoundError(selector)
        return elem

    async def get_element_by_text(self, text: str):
        """get element by text content, raise error if not found"""
        elem = await self._session.page.find(text, best_match=True)
        if elem is None:
            raise ElementNotFoundError(f"text='{text}'")
        return elem

    async def run_js(self, script: str) -> Any:
        """execute JavaScript and return result"""
        return await self._session.page.evaluate(script)

    async def check_visibility(self, selector: str) -> dict:
        """check if element exists and is visible"""
        safe_sel = self.escape_js_string(selector)
        return await self.run_js(f'''
            (function() {{
                const el = document.querySelector("{safe_sel}");
                if (!el) return {{ found: false }};
                const style = window.getComputedStyle(el);
                const hidden = style.display === "none" || style.visibility === "hidden";
                return {{ found: true, hidden: hidden, tag: el.tagName }};
            }})()
        ''')

    async def wait_for_condition(
        self,
        check_fn: Callable,
        timeout: float,
        poll_interval: float = 0.5
    ) -> bool:
        """wait for a condition to be true within timeout"""
        start = time.time()
        while time.time() - start < timeout:
            if await check_fn():
                return True
            await self._session.page.wait(poll_interval)
        return False

    @staticmethod
    def truncate(text: str, max_length: int, suffix: str = "\n... (truncated)") -> str:
        """truncate text if it exceeds max length"""
        if len(text) > max_length:
            return text[:max_length] + suffix
        return text

    @staticmethod
    def bool_to_yes_no(value: bool) -> str:
        """convert boolean to Yes/No string"""
        return "Yes" if value else "No"
