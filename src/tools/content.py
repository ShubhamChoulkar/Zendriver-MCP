# page content tools - get html, get text, scroll
from src.tools.base import ToolBase


class ContentTools(ToolBase):
    """tools for page content and scrolling"""

    def _register_tools(self) -> None:
        """register content tools"""
        self._register(self.get_content)
        self._register(self.get_text_content)
        self._register(self.get_interaction_tree)
        self._register(self.scroll)
        self._register(self.scroll_to_element)

    async def get_content(self, max_chars: int = 10000, offset: int = 0) -> str:
        """Get the page HTML, ``max_chars`` chars from ``offset``.

        The first line reports the slice, total size, and the next offset
        when more content is available.
        """
        content = await self.session.page.get_content()
        return self._paginate(content, max_chars, offset)

    async def get_text_content(self, max_chars: int = 10000, offset: int = 0) -> str:
        """Get visible page text; same pagination contract as get_content."""
        text = await self.run_js("document.body.innerText")
        return self._paginate(str(text), max_chars, offset)

    @staticmethod
    def _paginate(text: str, max_chars: int, offset: int) -> str:
        """Slice ``text`` with a one-line header so agents can paginate."""
        max_chars = max(1, max_chars)
        offset = max(0, offset)
        total = len(text)
        chunk = text[offset : offset + max_chars]
        end = offset + len(chunk)
        header = f"[chars {offset}-{end} of {total}]"
        if end < total:
            header += f" (next: offset={end})"
        return f"{header}\n{chunk}"

    async def get_interaction_tree(self, limit: int = 150) -> str:
        """List interactive elements as compact JSON with numeric ids.

        The ids double as selectors for click/type tools. ``limit`` caps
        the element count.
        """
        import json
        import os

        script_path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "dom_walker.js")
        if not os.path.exists(script_path):
            return "Error: dom_walker.js not found in static/js"

        with open(script_path, encoding="utf-8") as f:
            js_code = f.read()

        try:
            tree = await self.run_js(js_code)
        except Exception as e:
            return f"Error analyzing page: {str(e)}"

        tree = tree or []
        limit = max(1, limit)
        total = len(tree)
        payload = json.dumps(tree[:limit], separators=(",", ":"))
        if total > limit:
            return f"[showing {limit} of {total} elements; raise limit for more]\n{payload}"
        return payload

    async def scroll(self, direction: str = "down", pixels: int = 500) -> str:
        """Scroll the page up or down by ``pixels`` (instant, not animated).

        Uses JavaScript ``window.scrollBy`` directly. The earlier implementation
        called zendriver's ``scroll_down`` which interprets its argument as a
        *percentage* of the viewport and animates via
        ``Input.synthesizeScrollGesture`` - turning e.g. 500 into five
        viewport-heights of smooth scrolling.
        """
        page = self.session.page
        if direction == "down":
            await page.evaluate(f"window.scrollBy(0, {int(pixels)})")
            return f"Scrolled down {pixels}px"
        elif direction == "up":
            await page.evaluate(f"window.scrollBy(0, -{int(pixels)})")
            return f"Scrolled up {pixels}px"
        return f"Invalid direction: {direction}"

    async def scroll_to_element(self, selector: str) -> str:
        """Scroll to bring an element into view, or raise if it's missing.

        Honest success / failure reporting: if no element matches the
        selector we raise ``ElementNotFoundError`` instead of silently
        no-op'ing with a fake "Scrolled to: ..." message.
        """
        await self.get_element(selector)
        safe_sel = self.escape_js_string(selector)
        await self.run_js(
            f'document.querySelector("{safe_sel}")'
            f'?.scrollIntoView({{behavior: "smooth", block: "center"}})'
        )
        return f"Scrolled to: {selector}"
