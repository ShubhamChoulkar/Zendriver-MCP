# base class for all tool modules
import asyncio
import functools
import inspect
import os
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.errors import ElementNotFoundError, ToolTimeoutError
from src.session import BrowserSession


def _default_timeout() -> float:
    """Read the fallback per-tool timeout from the environment (seconds)."""
    raw = os.environ.get("ZENDRIVER_MCP_TOOL_TIMEOUT", "60")
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 60.0


DEFAULT_TOOL_TIMEOUT = _default_timeout()

# Must match ``ATTR`` in src/static/js/dom_walker.js.
ZENDRIVER_ID_ATTR = "data-zendriver-id"


class ToolBase(ABC):
    """base class providing shared functionality for all tool modules"""

    def __init__(self, mcp: FastMCP):
        self._mcp = mcp
        self._session = BrowserSession.get_instance()
        # Auto-register the tool's session-reset hook if it defines one.
        # Stateful tools (interception rules, trace buffers, screencast
        # handles, accessibility uid caches) implement ``_reset_state``;
        # this saves every such subclass from repeating the registration.
        reset = getattr(self, "_reset_state", None)
        if callable(reset):
            self._session.register_reset_callback(reset)
        self._register_tools()

    @staticmethod
    def resolve_selector(selector: str) -> str:
        """Turn a numeric id from ``get_interaction_tree`` into a CSS selector.

        The DOM walker tags interactive elements with ``data-zendriver-id``;
        tools accept either a real CSS selector or that numeric id. This
        helper centralises the conversion so every tool treats them the
        same way.
        """
        if selector.isdigit():
            return f'[{ZENDRIVER_ID_ATTR}="{selector}"]'
        return selector

    @abstractmethod
    def _register_tools(self) -> None:
        """register this module's tools with the mcp server"""

    def _register(
        self,
        fn: Callable[..., Coroutine[Any, Any, Any]],
        timeout: float | None = None,
    ) -> None:
        """Register ``fn`` as an MCP tool, guarded by a time budget.

        Every tool gets wrapped in :func:`asyncio.wait_for` so one hung CDP
        call can never freeze the whole MCP session. The budget defaults to
        ``DEFAULT_TOOL_TIMEOUT`` (60s, or the ``ZENDRIVER_MCP_TOOL_TIMEOUT``
        env var) and can be overridden per tool when a particular operation
        is known to be slow (tracing, heap snapshots, Lighthouse, ...).
        """
        budget = float(timeout) if timeout is not None else DEFAULT_TOOL_TIMEOUT
        name = fn.__name__

        @functools.wraps(fn)
        async def guarded(*args: Any, **kwargs: Any) -> Any:
            try:
                return await asyncio.wait_for(fn(*args, **kwargs), timeout=budget)
            except asyncio.TimeoutError as exc:
                raise ToolTimeoutError(name, budget) from exc

        # Preserve the original signature so FastMCP still introspects the
        # right schema; wait_for+wraps keeps the coroutine type alive.
        guarded.__signature__ = inspect.signature(fn)  # type: ignore[attr-defined]
        # Delete __wrapped__ so FastMCP's introspection doesn't follow it
        # back to the unbound function (which would expose `self` in the
        # schema and make the tool uncallable from the client).
        if hasattr(guarded, "__wrapped__"):
            delattr(guarded, "__wrapped__")
        # Marker so tests and tooling can verify the guard is in place.
        guarded.__zendriver_timeout__ = budget  # type: ignore[attr-defined]
        self._mcp.tool()(guarded)

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
        return (
            s.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("'", "\\'")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )

    async def get_element(self, selector: str, timeout: float = 2.0):
        """Get element by selector or raise ``ElementNotFoundError`` fast.

        Zendriver's ``page.select`` raises ``asyncio.TimeoutError`` after a
        10s default wait when the element is missing. Catching that here and
        raising our typed error means agents see "not found" in ~2s instead
        of waiting 10s and getting a raw TimeoutError.
        """
        try:
            return await self._session.page.select(selector, timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise ElementNotFoundError(selector) from exc

    async def get_element_by_text(self, text: str, timeout: float = 2.0):
        """Find element by visible text, typed error on miss, no 10s hang."""
        try:
            return await self._session.page.find(text, best_match=True, timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise ElementNotFoundError(f"text='{text}'") from exc

    async def try_select(self, selector: str, timeout: float = 2.0):
        """Select an element, return ``None`` on miss instead of raising.

        Use this when the upstream logic legitimately wants to branch on
        presence (e.g. a visibility probe before clicking).
        """
        try:
            return await self._session.page.select(selector, timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def run_js(self, script: str) -> Any:
        """execute JavaScript and return result"""
        return await self._session.page.evaluate(script)

    async def check_visibility(self, selector: str) -> dict:
        """check if element exists and is visible

        Also treats a zero-size bounding rect as hidden. Outlook and
        similar SPAs render several ``[role="searchbox"]`` elements in
        the DOM - only one of them has an actual rect, the others are
        display: block with 0x0 dimensions. Accepting those as visible
        caused ``click`` to silently "succeed" while focus stayed where
        it was, and ``type_text`` routed keystrokes to whichever other
        element held focus.
        """
        safe_sel = self.escape_js_string(selector)
        return await self.run_js(f'''
            (function() {{
                const el = document.querySelector("{safe_sel}");
                if (!el) return {{ found: false }};
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                const zero_size = rect.width === 0 && rect.height === 0;
                const hidden = style.display === "none" || style.visibility === "hidden" || zero_size;
                return {{
                    found: true,
                    hidden: hidden,
                    zero_size: zero_size,
                    tag: el.tagName,
                }};
            }})()
        ''')

    async def wait_for_condition(
        self, check_fn: Callable, timeout: float, poll_interval: float = 0.5
    ) -> bool:
        """wait for a condition to be true within timeout"""
        start = time.time()
        while time.time() - start < timeout:
            if await check_fn():
                return True
            await self._session.page.wait(poll_interval)
        return False

    @staticmethod
    def bool_to_yes_no(value: bool) -> str:
        """convert boolean to Yes/No string"""
        return "Yes" if value else "No"
