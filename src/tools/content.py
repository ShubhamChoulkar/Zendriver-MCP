# page content tools - get html, get text, scroll, tables, structured data
import json
from src.tools.base import ToolBase


class ContentTools(ToolBase):
    """tools for page content and scrolling"""

    def _register_tools(self) -> None:
        """register content tools"""
        self._mcp.tool()(self.get_content)
        self._mcp.tool()(self.get_text_content)
        self._mcp.tool()(self.get_interaction_tree)
        self._mcp.tool()(self.get_links)
        self._mcp.tool()(self.extract_table)
        self._mcp.tool()(self.extract_structured_data)
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

    async def get_links(self, filter_text: str = "", internal_only: bool = False) -> str:
        """Get all links from the page.

        Args:
            filter_text: Optional text filter to match in URL or link text
            internal_only: If True, only return links to the same domain
        """
        safe_filter = self.escape_js_string(filter_text) if filter_text else ""

        links = await self.run_js(f'''
            (function() {{
                const filter = "{safe_filter}".toLowerCase();
                const internalOnly = {'true' if internal_only else 'false'};
                const currentHost = location.hostname;
                const results = [];
                const seen = new Set();

                for (const a of document.querySelectorAll("a[href]")) {{
                    const href = a.href;
                    if (!href || href.startsWith("javascript:")) continue;
                    if (seen.has(href)) continue;
                    seen.add(href);

                    const text = (a.innerText || a.getAttribute("aria-label") || "").trim().substring(0, 60);
                    if (filter && !href.toLowerCase().includes(filter) && !text.toLowerCase().includes(filter)) continue;

                    let isInternal = false;
                    try {{
                        isInternal = new URL(href).hostname === currentHost;
                    }} catch(e) {{
                        isInternal = href.startsWith("/") || href.startsWith("#");
                    }}

                    if (internalOnly && !isInternal) continue;

                    results.push({{
                        text: text || "(no text)",
                        href: href.substring(0, 150),
                        internal: isInternal
                    }});
                }}

                return results;
            }})()
        ''')

        if not links:
            return "No links found" + (f" matching '{filter_text}'" if filter_text else "")

        lines = [f"Found {len(links)} link(s):"]
        for i, link in enumerate(links[:50]):
            scope = "internal" if link['internal'] else "external"
            lines.append(f"  {i+1}. [{scope}] {link['text']} -> {link['href']}")

        if len(links) > 50:
            lines.append(f"  ... and {len(links) - 50} more")

        return "\n".join(lines)

    async def extract_table(self, selector: str = "table", format: str = "json") -> str:
        """Extract table data as clean structured JSON or readable markdown.

        Strips away all HTML tags and returns only the data.

        Args:
            selector: CSS selector for table(s) to extract (default: all tables)
            format: 'json' for structured data, 'markdown' for readable format
        """
        safe_sel = self.escape_js_string(selector)
        data = await self.run_js(f'''
            (function() {{
                const tables = document.querySelectorAll("{safe_sel}");
                if (!tables.length) return null;
                const results = [];
                for (const table of tables) {{
                    const headers = [];
                    const rows = [];
                    const ths = table.querySelectorAll("thead th, thead td");
                    ths.forEach(th => headers.push(th.innerText.trim()));
                    const trs = table.querySelectorAll("tbody tr");
                    if (trs.length) {{
                        trs.forEach(tr => {{
                            const cells = [];
                            tr.querySelectorAll("td, th").forEach(td => cells.push(td.innerText.trim()));
                            if (cells.length) rows.push(cells);
                        }});
                    }} else {{
                        const allTrs = table.querySelectorAll("tr");
                        let startIdx = 0;
                        if (!headers.length && allTrs.length) {{
                            allTrs[0].querySelectorAll("th, td").forEach(c => headers.push(c.innerText.trim()));
                            startIdx = 1;
                        }}
                        for (let i = startIdx; i < allTrs.length; i++) {{
                            const cells = [];
                            allTrs[i].querySelectorAll("td, th").forEach(td => cells.push(td.innerText.trim()));
                            if (cells.length) rows.push(cells);
                        }}
                    }}
                    results.push({{ headers, rows, rowCount: rows.length }});
                }}
                return results;
            }})()
        ''')

        if not data:
            return f"No tables found matching: {selector}"

        if format == "markdown":
            parts = []
            for i, table in enumerate(data):
                if len(data) > 1:
                    parts.append(f"### Table {i+1}")
                if table['headers']:
                    parts.append("| " + " | ".join(table['headers']) + " |")
                    parts.append("|" + "|".join(["---"] * len(table['headers'])) + "|")
                for row in table['rows']:
                    parts.append("| " + " | ".join(row) + " |")
                parts.append(f"\n{table['rowCount']} row(s)")
            return "\n".join(parts)
        else:
            return json.dumps(data, indent=2)

    async def extract_structured_data(self) -> str:
        """Extract structured metadata from the page: JSON-LD, OpenGraph, and meta tags.

        Returns machine-readable data that websites embed for search engines and social media.
        Much more reliable than scraping visible text.
        """
        data = await self.run_js('''
            (function() {
                const result = { jsonld: [], opengraph: {}, twitter: {}, meta: {} };
                document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
                    try { result.jsonld.push(JSON.parse(s.textContent)); } catch(e) {}
                });
                document.querySelectorAll('meta[property^="og:"]').forEach(m => {
                    result.opengraph[m.getAttribute("property")] = m.content;
                });
                document.querySelectorAll('meta[name^="twitter:"]').forEach(m => {
                    result.twitter[m.name] = m.content;
                });
                document.querySelectorAll('meta[name]').forEach(m => {
                    const name = m.name.toLowerCase();
                    if (!name.startsWith("og:") && !name.startsWith("twitter:")) {
                        result.meta[name] = m.content;
                    }
                });
                result.meta.title = document.title;
                const canonical = document.querySelector('link[rel="canonical"]');
                if (canonical) result.meta.canonical = canonical.href;
                return result;
            })()
        ''')

        if not data:
            return "No structured data found on this page."
        return json.dumps(data, indent=2)
