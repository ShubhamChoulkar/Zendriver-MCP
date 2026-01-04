# element query tools - find element, find all, get text, get attribute, find buttons
from typing import Optional

from src.tools.base import ToolBase


class QueryTools(ToolBase):
    """tools for querying and inspecting elements"""

    def _register_tools(self) -> None:
        """register element query tools"""
        self._mcp.tool()(self.find_element)
        self._mcp.tool()(self.find_all_elements)
        self._mcp.tool()(self.get_element_text)
        self._mcp.tool()(self.get_element_attribute)
        self._mcp.tool()(self.find_buttons)
        self._mcp.tool()(self.find_inputs)

    async def find_element(self, selector: Optional[str] = None, text: Optional[str] = None) -> str:
        """Find an element and return information about it.

        Provides helpful suggestions if element is not found.
        """
        page = self.session.page

        if selector:
            try:
                elem = await page.select(selector, timeout=2)
            except Exception:
                elem = None

            if elem is None:
                # provide helpful suggestions
                suggestions = await self.run_js('''
                    (function() {
                        const found = [];
                        const ce = document.querySelector('[contenteditable="true"]');
                        if (ce) found.push({ sel: '[contenteditable="true"]', tag: ce.tagName });
                        const tb = document.querySelector('[role="textbox"]');
                        if (tb) found.push({ sel: '[role="textbox"]', tag: tb.tagName });
                        const ta = document.querySelector('textarea');
                        if (ta) found.push({ sel: 'textarea', tag: 'TEXTAREA' });
                        const inp = document.querySelector('input:not([type="hidden"])');
                        if (inp) found.push({ sel: 'input', tag: 'INPUT', type: inp.type });
                        const btn = document.querySelector('button');
                        if (btn) found.push({ sel: 'button', tag: 'BUTTON' });
                        return found.slice(0, 5);
                    })()
                ''')

                msg = f"Element not found: {selector}"
                if suggestions:
                    suggestions_text = ", ".join([s['sel'] for s in suggestions])
                    msg += f"\nAvailable interactive elements: {suggestions_text}"
                return msg

            tag = getattr(elem, "tag_name", "unknown")
            text_content = getattr(elem, "text", "") or ""

            # get additional useful info
            safe_sel = self.escape_js_string(selector)
            extra_info = await self.run_js(f'''
                (function() {{
                    const el = document.querySelector("{safe_sel}");
                    if (!el) return {{}};
                    const style = window.getComputedStyle(el);
                    return {{
                        visible: style.display !== "none" && style.visibility !== "hidden",
                        editable: el.isContentEditable || el.tagName === "INPUT" || el.tagName === "TEXTAREA",
                        clickable: el.tagName === "BUTTON" || el.tagName === "A" || el.onclick !== null
                    }};
                }})()
            ''')

            visibility = "visible" if extra_info.get('visible', True) else "HIDDEN"
            return f"Found <{tag}> ({visibility}): {text_content[:200] if text_content else '(no text)'}"

        elif text:
            elem = await page.find(text, best_match=True)
            if elem is None:
                return f"Element not found with text: {text}"
            tag = getattr(elem, "tag_name", "unknown")
            return f"Found <{tag}> matching: {text}"

        return "Error: Provide selector or text"

    async def find_all_elements(self, selector: str, limit: int = 20) -> str:
        """Find all elements matching a selector."""
        elems = await self.session.page.select_all(selector)
        if not elems:
            return f"No elements found: {selector}"

        results = []
        for i, elem in enumerate(elems[:limit]):
            tag = getattr(elem, "tag_name", "unknown")
            text = (getattr(elem, "text", "") or "")[:50]
            results.append(f"{i+1}. <{tag}> {text}")

        total, shown = len(elems), min(len(elems), limit)
        return f"Found {total} element(s) (showing {shown}):\n" + "\n".join(results)

    async def get_element_text(self, selector: str) -> str:
        """Get the text content of an element."""
        elem = await self.get_element(selector)
        text = getattr(elem, "text", "") or ""
        return text if text else "(empty)"

    async def get_element_attribute(self, selector: str, attribute: str) -> str:
        """Get an attribute value from an element."""
        elem = await self.get_element(selector)
        attrs = getattr(elem, "attrs", {})
        value = attrs.get(attribute) if attrs else None
        return str(value) if value else "(not set)"

    async def find_buttons(self, filter_text: Optional[str] = None) -> str:
        """Find all clickable buttons on the page, including icon-only buttons.

        Detects: button tags, input[type=submit], [role=button], clickable divs/spans with icons.
        Returns selector and description for each button found.
        """
        safe_filter = self.escape_js_string(filter_text) if filter_text else ""

        buttons = await self.run_js(f'''
            (function() {{
                const filter = "{safe_filter}".toLowerCase();
                const results = [];

                // helper to get button description
                function getDescription(el) {{
                    // check text content
                    const text = el.innerText?.trim();
                    if (text) return text;

                    // check aria-label
                    const ariaLabel = el.getAttribute("aria-label");
                    if (ariaLabel) return ariaLabel;

                    // check title
                    const title = el.getAttribute("title");
                    if (title) return title;

                    // check for icon (svg, img, i tag)
                    const svg = el.querySelector("svg");
                    if (svg) {{
                        const svgTitle = svg.querySelector("title")?.textContent;
                        if (svgTitle) return "Icon: " + svgTitle;
                        const use = svg.querySelector("use");
                        if (use) {{
                            const href = use.getAttribute("href") || use.getAttribute("xlink:href");
                            if (href) return "Icon: " + href.split("#").pop();
                        }}
                        return "Icon button";
                    }}

                    const img = el.querySelector("img");
                    if (img) return "Image: " + (img.alt || img.src.split("/").pop());

                    const icon = el.querySelector("i, span[class*='icon']");
                    if (icon) return "Icon: " + (icon.className || "unknown");

                    return "(no description)";
                }}

                // helper to escape CSS selector special characters
                function escapeCSS(str) {{
                    return str.replace(/([!"#$%&'()*+,./:;<=>?@[\\]^`{{|}}~])/g, '\\\\$1');
                }}

                // helper to check if class is valid for CSS selector
                function isValidClass(c) {{
                    // skip Tailwind responsive/state prefixes and complex classes
                    if (c.includes(':') || c.includes('[') || c.includes(']') || c.includes('/')) return false;
                    if (c.includes('hover') || c.includes('active') || c.includes('focus') || c.includes('visible')) return false;
                    // skip classes with special CSS chars that would need escaping
                    if (/[!"#$%&'()*+,./:;<=>?@\\^`{{|}}~]/.test(c)) return false;
                    // skip very short generic classes or very long ones
                    if (c.length < 2 || c.length > 30) return false;
                    // must start with a letter or hyphen
                    if (!/^[a-zA-Z_-]/.test(c)) return false;
                    return true;
                }}

                // helper to get unique selector
                function getSelector(el) {{
                    // prefer ID
                    if (el.id) return "#" + escapeCSS(el.id);

                    // prefer name attribute
                    if (el.name) return el.tagName.toLowerCase() + "[name='" + el.name + "']";

                    // try aria-label
                    const ariaLabel = el.getAttribute("aria-label");
                    if (ariaLabel && ariaLabel.length < 50) {{
                        const sel = el.tagName.toLowerCase() + "[aria-label='" + ariaLabel.replace(/'/g, "\\'") + "']";
                        try {{
                            if (document.querySelectorAll(sel).length === 1) return sel;
                        }} catch(e) {{}}
                    }}

                    // try data-testid or data-id
                    const testId = el.getAttribute("data-testid") || el.getAttribute("data-id");
                    if (testId) {{
                        return el.tagName.toLowerCase() + "[data-testid='" + testId + "']";
                    }}

                    // try simple classes only (no Tailwind prefixes)
                    const classes = Array.from(el.classList).filter(isValidClass);
                    if (classes.length > 0) {{
                        const escapedClasses = classes.slice(0, 2).map(escapeCSS).join(".");
                        const sel = el.tagName.toLowerCase() + "." + escapedClasses;
                        try {{
                            if (document.querySelectorAll(sel).length === 1) return sel;
                        }} catch(e) {{}}
                    }}

                    // fallback: use data attributes
                    for (const attr of el.attributes) {{
                        if (attr.name.startsWith("data-") && attr.value && attr.value.length < 50) {{
                            const sel = el.tagName.toLowerCase() + "[" + attr.name + "='" + attr.value.replace(/'/g, "\\'") + "']";
                            try {{
                                if (document.querySelectorAll(sel).length === 1) return sel;
                            }} catch(e) {{}}
                        }}
                    }}

                    // last resort: nth-of-type
                    const parent = el.parentElement;
                    if (parent) {{
                        const siblings = Array.from(parent.children).filter(c => c.tagName === el.tagName);
                        const index = siblings.indexOf(el) + 1;
                        return el.tagName.toLowerCase() + ":nth-of-type(" + index + ")";
                    }}

                    return el.tagName.toLowerCase();
                }}

                // find all button-like elements
                const selectors = [
                    "button",
                    "input[type='submit']",
                    "input[type='button']",
                    "[role='button']",
                    "a[href='#']",
                    "a[href='javascript:']",
                    "[onclick]"
                ];

                const seen = new Set();
                for (const sel of selectors) {{
                    for (const el of document.querySelectorAll(sel)) {{
                        if (seen.has(el)) continue;
                        seen.add(el);

                        const style = window.getComputedStyle(el);
                        if (style.display === "none" || style.visibility === "hidden") continue;

                        const desc = getDescription(el);
                        if (filter && !desc.toLowerCase().includes(filter)) continue;

                        results.push({{
                            selector: getSelector(el),
                            tag: el.tagName,
                            description: desc.substring(0, 50),
                            type: el.type || el.getAttribute("role") || "button"
                        }});
                    }}
                }}

                return results.slice(0, 20);
            }})()
        ''')

        if not buttons:
            return "No buttons found" + (f" matching '{filter_text}'" if filter_text else "")

        lines = [f"Found {len(buttons)} button(s):"]
        for i, btn in enumerate(buttons):
            lines.append(f"  {i+1}. [{btn['type']}] {btn['description']} -> {btn['selector']}")

        return "\n".join(lines)

    async def find_inputs(self, filter_type: Optional[str] = None) -> str:
        """Find all input fields on the page with their selectors.

        Detects: input, textarea, contenteditable, [role=textbox], search boxes.
        filter_type: optional filter like 'text', 'search', 'password', 'email'
        """
        safe_filter = self.escape_js_string(filter_type) if filter_type else ""

        inputs = await self.run_js(f'''
            (function() {{
                const filter = "{safe_filter}".toLowerCase();
                const results = [];

                function getSelector(el) {{
                    if (el.id) return "#" + el.id;
                    if (el.name) return el.tagName.toLowerCase() + "[name='" + el.name + "']";
                    if (el.placeholder) return el.tagName.toLowerCase() + "[placeholder='" + el.placeholder.substring(0, 30) + "']";

                    const classes = Array.from(el.classList || []).filter(c => c.length < 30);
                    if (classes.length > 0) return el.tagName.toLowerCase() + "." + classes[0];

                    return el.tagName.toLowerCase();
                }}

                function getDescription(el) {{
                    const label = document.querySelector("label[for='" + el.id + "']");
                    if (label) return label.textContent.trim();
                    if (el.placeholder) return el.placeholder;
                    if (el.ariaLabel) return el.ariaLabel;
                    return el.name || el.type || "input";
                }}

                // standard inputs
                for (const el of document.querySelectorAll("input, textarea")) {{
                    const style = window.getComputedStyle(el);
                    if (style.display === "none" || el.type === "hidden") continue;

                    const inputType = el.type || "text";
                    if (filter && !inputType.includes(filter)) continue;

                    results.push({{
                        selector: getSelector(el),
                        type: inputType,
                        description: getDescription(el).substring(0, 40)
                    }});
                }}

                // contenteditable and role=textbox
                for (const el of document.querySelectorAll('[contenteditable="true"], [role="textbox"]')) {{
                    const style = window.getComputedStyle(el);
                    if (style.display === "none") continue;

                    if (filter && !["text", "contenteditable", "textbox"].some(t => t.includes(filter))) continue;

                    results.push({{
                        selector: getSelector(el),
                        type: el.getAttribute("role") || "contenteditable",
                        description: el.ariaLabel || el.placeholder || "rich text editor"
                    }});
                }}

                return results.slice(0, 20);
            }})()
        ''')

        if not inputs:
            return "No input fields found" + (f" of type '{filter_type}'" if filter_type else "")

        lines = [f"Found {len(inputs)} input(s):"]
        for i, inp in enumerate(inputs):
            lines.append(f"  {i+1}. [{inp['type']}] {inp['description']} -> {inp['selector']}")

        return "\n".join(lines)
