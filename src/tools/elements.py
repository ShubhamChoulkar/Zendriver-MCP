# element interaction tools - click, type, clear, focus, select, upload
from typing import Optional

from zendriver import cdp

from src.tools.base import ToolBase
from src.errors import ElementNotFoundError


class ElementTools(ToolBase):
    """tools for interacting with page elements"""

    def _register_tools(self) -> None:
        """register element interaction tools"""
        self._mcp.tool()(self.click)
        self._mcp.tool()(self.type_text)
        self._mcp.tool()(self.clear_input)
        self._mcp.tool()(self.focus_element)
        self._mcp.tool()(self.select_option)
        self._mcp.tool()(self.upload_file)
        self._mcp.tool()(self.highlight_element)
        self._mcp.tool()(self.hide_element)
        self._mcp.tool()(self.remove_element)

    async def click(self, selector: Optional[str] = None, text: Optional[str] = None) -> str:
        """Click a visible element by CSS selector, numeric ID (from get_interaction_tree), or text content."""
        self._record("click", selector=selector, text=text)
        if selector:
            if selector.isdigit():
                selector = f'[data-zendriver-id="{selector}"]'

            check = await self.check_visibility(selector)
            if not check['found']:
                if '[data-zendriver-id=' in selector:
                     return "Error: ID not found. The page may have changed. Please run get_interaction_tree() again."
                raise ElementNotFoundError(selector)
            if check.get('hidden'):
                return f"Error: Element '{selector}' is hidden. Cannot click."
            elem = await self.session.page.select(selector)
            if elem:
                await elem.click()
                return f"Clicked: {selector}"
            raise ElementNotFoundError(selector)
        elif text:
            elem = await self.get_element_by_text(text)
            await elem.click()
            return f"Clicked: {text}"
        return "Error: Provide selector or text"

    async def type_text(self, text: str, selector: str) -> str:
        """Type text into an element using CDP Input.insertText (no JS).

        Works with contenteditable divs, shadow DOM inputs, and standard form fields.
        """
        self._record("type_text", text=text, selector=selector)
        # Make selector consistent
        if selector.isdigit():
            selector = f'[data-zendriver-id="{selector}"]'

        # Focus the element by clicking it
        elem = await self.get_element(selector)
        await elem.click()

        try:
            # Use CDP Input.insertText for reliable input into
            # contenteditable elements and shadow DOM
            await self.session.page.send(cdp.input_.insert_text(text=text))
        except Exception:
            # Fallback to send_keys if CDP insertText is unavailable
            await elem.send_keys(text)

        return f"Typed into {selector}"



    async def clear_input(self, selector: str) -> str:
        """Clear an input field or contenteditable element."""
        if selector.isdigit():
            selector = f'[data-zendriver-id="{selector}"]'

        elem = await self.session.page.select(selector)
        if not elem:
            return f"Error: Element not found - {selector}"

        # Select all and delete
        await elem.apply("(el) => { el.focus(); document.execCommand('selectAll'); document.execCommand('delete'); }")
        return f"Cleared: {selector}"

    async def focus_element(self, selector: str) -> str:
        """Focus on an element."""
        if selector.isdigit():
            selector = f'[data-zendriver-id="{selector}"]'

        elem = await self.get_element(selector)
        await elem.focus()
        return f"Focused on: {selector}"

    async def select_option(self, selector: str, value: str) -> str:
        """Select an option from a dropdown."""
        if selector.isdigit():
            selector = f'[data-zendriver-id="{selector}"]'

        await self.get_element(selector)
        safe_sel = self.escape_js_string(selector)
        safe_val = self.escape_js_string(value)
        await self.run_js(f'''
            const select = document.querySelector("{safe_sel}");
            select.value = "{safe_val}";
            select.dispatchEvent(new Event("change", {{ bubbles: true }}));
        ''')
        return f"Selected '{value}' in: {selector}"

    async def upload_file(self, selector: str, file_path: str) -> str:
        """Upload a file to a file input."""
        if selector.isdigit():
            selector = f'[data-zendriver-id="{selector}"]'

        elem = await self.get_element(selector)
        await elem.send_file(file_path)
        return f"Uploaded file '{file_path}' to: {selector}"

    async def highlight_element(self, selector: str, color: str = "red", duration: float = 3.0) -> str:
        """Highlight an element on the page for visual debugging.

        Adds a bright colored outline around the element that auto-removes after the duration.

        Args:
            selector: CSS selector or numeric ID from get_interaction_tree
            color: Outline color (default: red)
            duration: How long to show the highlight in seconds (default: 3)
        """
        if selector.isdigit():
            selector = f'[data-zendriver-id="{selector}"]'

        safe_sel = self.escape_js_string(selector)
        safe_color = self.escape_js_string(color)

        result = await self.run_js(f'''
            (function() {{
                const el = document.querySelector("{safe_sel}");
                if (!el) return {{ found: false }};

                const prev = el.style.cssText;
                el.style.outline = "3px solid {safe_color}";
                el.style.outlineOffset = "2px";
                el.style.boxShadow = "0 0 10px {safe_color}";

                setTimeout(() => {{
                    el.style.cssText = prev;
                }}, {int(duration * 1000)});

                const rect = el.getBoundingClientRect();
                return {{
                    found: true,
                    tag: el.tagName,
                    text: (el.innerText || "").substring(0, 50),
                    position: `${{Math.round(rect.x)}},${{Math.round(rect.y)}} (${{Math.round(rect.width)}}x${{Math.round(rect.height)}})`
                }};
            }})()
        ''')

        if not result or not result.get('found'):
            return f"Element not found: {selector}"

        return (
            f"Highlighted <{result['tag']}> at {result['position']}\n"
            f"Text: {result.get('text', '(none)')}"
        )

    async def hide_element(self, selector: str) -> str:
        """Hide an element by setting display:none. Useful for removing popups/overlays.

        Args:
            selector: CSS selector or numeric ID from get_interaction_tree
        """
        if selector.isdigit():
            selector = f'[data-zendriver-id="{selector}"]'

        safe_sel = self.escape_js_string(selector)
        count = await self.run_js(f'''
            (function() {{
                const els = document.querySelectorAll("{safe_sel}");
                els.forEach(el => el.style.display = "none");
                return els.length;
            }})()
        ''')

        if not count:
            return f"No elements found to hide: {selector}"
        return f"Hidden {count} element(s): {selector}"

    async def remove_element(self, selector: str) -> str:
        """Remove an element from the DOM entirely. Useful for cookie banners, ads, etc.

        Args:
            selector: CSS selector or numeric ID from get_interaction_tree
        """
        if selector.isdigit():
            selector = f'[data-zendriver-id="{selector}"]'

        safe_sel = self.escape_js_string(selector)
        count = await self.run_js(f'''
            (function() {{
                const els = document.querySelectorAll("{safe_sel}");
                els.forEach(el => el.remove());
                return els.length;
            }})()
        ''')

        if not count:
            return f"No elements found to remove: {selector}"
        return f"Removed {count} element(s): {selector}"
