# page content tools - get html, get text, scroll
from src.tools.base import ToolBase


class ContentTools(ToolBase):
    """tools for page content and scrolling"""

    def _register_tools(self) -> None:
        """register content tools"""
        self._mcp.tool()(self.get_content)
        self._mcp.tool()(self.get_text_content)
        self._mcp.tool()(self.get_interaction_tree)
        self._mcp.tool()(self.scroll)
        self._mcp.tool()(self.scroll_to_element)

    async def get_content(self) -> str:
        """Get the full HTML content of the page."""
        content = await self.session.page.get_content()
        return self.truncate(content, 50000)

    async def get_text_content(self) -> str:
        """Get all visible text from the page."""
        text = await self.run_js('document.body.innerText')
        return self.truncate(text, 30000)

    async def get_interaction_tree(self) -> str:
        """Get a simplified tree of interactive elements with unique IDs.
        
        Uses a sophisticated heuristic to find interactive elements (buttons, inputs, 
        shadow DOM components), assigns them unique IDs, and returns a clean list.
        """
        import json
        import os
        
        # Load the JS walker script
        script_path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "dom_walker.js")
        if not os.path.exists(script_path):
            return "Error: dom_walker.js not found in static/js"
            
        with open(script_path, "r", encoding="utf-8") as f:
            js_code = f.read()

        try:
            tree = await self.run_js(js_code)
            return json.dumps(tree, indent=2)
        except Exception as e:
            return f"Error analyzing page: {str(e)}"

    async def scroll(self, direction: str = "down", amount: int = 500) -> str:
        """Scroll the page up or down."""
        page = self.session.page
        if direction == "down":
            await page.scroll_down(amount)
            return f"Scrolled down {amount}px"
        elif direction == "up":
            await page.scroll_up(amount)
            return f"Scrolled up {amount}px"
        return f"Invalid direction: {direction}"

    async def scroll_to_element(self, selector: str) -> str:
        """Scroll to bring an element into view."""
        safe_sel = self.escape_js_string(selector)
        await self.run_js(f'document.querySelector("{safe_sel}")?.scrollIntoView({{behavior: "smooth", block: "center"}})')
        return f"Scrolled to: {selector}"
