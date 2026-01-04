# form and input tools - fill form, submit, keyboard, mouse
import json
from typing import Optional

from src.tools.base import ToolBase


class FormTools(ToolBase):
    """tools for forms and input handling"""

    def _register_tools(self) -> None:
        """register form and input tools"""
        self._mcp.tool()(self.fill_form)
        self._mcp.tool()(self.submit_form)
        self._mcp.tool()(self.press_key)
        self._mcp.tool()(self.press_enter)
        self._mcp.tool()(self.mouse_click)

    async def fill_form(self, form_data: str) -> str:
        """Fill a form with multiple fields. Pass JSON like '{"#email": "test@test.com"}'."""
        data = json.loads(form_data)
        filled = []

        for selector, value in data.items():
            elem = await self.session.page.select(selector)
            if elem:
                await elem.clear_input()
                await elem.send_keys(str(value))
                filled.append(selector)

        return f"Filled {len(filled)} field(s): {', '.join(filled)}"

    async def submit_form(self, selector: str = "form") -> str:
        """Submit a form."""
        safe_sel = self.escape_js_string(selector)
        await self.run_js(f'document.querySelector("{safe_sel}")?.submit()')
        return f"Form submitted: {selector}"

    async def press_key(self, key: str, selector: Optional[str] = None) -> str:
        """Press a keyboard key with full event simulation.

        Args:
            key: Key to press (e.g., 'Enter', 'Tab', 'Escape', 'a', 'Backspace')
            selector: Optional element selector to send key to (defaults to active element)

        Properly triggers keydown, keypress, and keyup events that frameworks listen to.
        """
        safe_key = self.escape_js_string(key)

        # map common key names to their codes
        key_codes = {
            'Enter': 13, 'Tab': 9, 'Escape': 27, 'Backspace': 8, 'Delete': 46,
            'ArrowUp': 38, 'ArrowDown': 40, 'ArrowLeft': 37, 'ArrowRight': 39,
            'Space': 32, ' ': 32, 'Home': 36, 'End': 35, 'PageUp': 33, 'PageDown': 34
        }

        if selector:
            safe_sel = self.escape_js_string(selector)
            target_js = f'document.querySelector("{safe_sel}")'
        else:
            target_js = 'document.activeElement'

        await self.run_js(f'''
            (function() {{
                const el = {target_js};
                if (!el) return;

                const key = "{safe_key}";
                const keyCode = {json.dumps(key_codes)};
                const code = keyCode[key] || key.charCodeAt(0);

                // create event options
                const eventOptions = {{
                    key: key,
                    code: key.length === 1 ? "Key" + key.toUpperCase() : key,
                    keyCode: code,
                    which: code,
                    charCode: key === "Enter" ? 13 : 0,
                    bubbles: true,
                    cancelable: true,
                    composed: true
                }};

                // dispatch keydown
                const keydownEvent = new KeyboardEvent("keydown", eventOptions);
                const keydownResult = el.dispatchEvent(keydownEvent);

                // dispatch keypress for character keys (deprecated but some frameworks need it)
                if (key.length === 1 || key === "Enter") {{
                    const keypressEvent = new KeyboardEvent("keypress", eventOptions);
                    el.dispatchEvent(keypressEvent);
                }}

                // special handling for Enter key
                if (key === "Enter") {{
                    // check if element is in a form
                    const form = el.closest("form");
                    if (form && el.tagName !== "TEXTAREA") {{
                        // trigger form submission
                        const submitEvent = new Event("submit", {{ bubbles: true, cancelable: true }});
                        const submitted = form.dispatchEvent(submitEvent);
                        if (submitted && !submitEvent.defaultPrevented) {{
                            // find submit button and click it, or submit form
                            const submitBtn = form.querySelector('[type="submit"], button:not([type="button"])');
                            if (submitBtn) {{
                                submitBtn.click();
                            }}
                        }}
                    }}
                    // also dispatch click on buttons
                    if (el.tagName === "BUTTON" || el.getAttribute("role") === "button") {{
                        el.click();
                    }}
                }}

                // special handling for Tab key
                if (key === "Tab" && keydownResult) {{
                    // move focus to next focusable element
                    const focusable = Array.from(document.querySelectorAll(
                        'button, [href], input:not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])'
                    )).filter(e => !e.disabled && e.offsetParent !== null);

                    const currentIndex = focusable.indexOf(el);
                    if (currentIndex !== -1 && currentIndex < focusable.length - 1) {{
                        focusable[currentIndex + 1].focus();
                    }}
                }}

                // dispatch keyup
                const keyupEvent = new KeyboardEvent("keyup", eventOptions);
                el.dispatchEvent(keyupEvent);
            }})()
        ''')
        return f"Pressed key: {key}" + (f" on {selector}" if selector else "")

    async def press_enter(self, selector: Optional[str] = None) -> str:
        """Press Enter key - convenience wrapper for press_key('Enter')."""
        return await self.press_key("Enter", selector)

    async def mouse_click(self, x: int, y: int) -> str:
        """Click at specific coordinates."""
        await self.session.page.mouse_click(x, y)
        return f"Clicked at ({x}, {y})"
