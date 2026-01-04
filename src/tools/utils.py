# utility tools - screenshot, js execution, waiting, security audit
import io
import json
import os
import tempfile
from datetime import datetime
from typing import Optional

from mcp.server.fastmcp.utilities.types import Image
from PIL import Image as PILImage

from src.tools.base import ToolBase


class UtilityTools(ToolBase):
    """utility tools for screenshots, js, waiting, and security"""

    def _register_tools(self) -> None:
        """register utility tools"""
        self._mcp.tool()(self.screenshot)
        self._mcp.tool()(self.execute_js)
        self._mcp.tool()(self.wait)
        self._mcp.tool()(self.wait_for_element)
        self._mcp.tool()(self.run_security_audit)

    async def screenshot(self, save_path: Optional[str] = None) -> Image:
        """Take a screenshot of the current page and return as viewable image.

        Args:
            save_path: Optional path to save the screenshot to disk (e.g., "screenshot.png").
                      If provided, saves the file and returns the image. If not provided,
                      only returns the image data without saving to disk.
        """
        if not self.session.page:
            # return red placeholder image with error
            img = PILImage.new("RGB", (400, 100), color=(200, 50, 50))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG")
            return Image(data=buffer.getvalue(), format="jpeg")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            await self.session.page.save_screenshot(tmp_path)
            # compress to JPEG for smaller size (under 1MB limit)
            with PILImage.open(tmp_path) as img:
                buffer = io.BytesIO()
                img.convert("RGB").save(buffer, format="JPEG", quality=60, optimize=True)
                jpeg_data = buffer.getvalue()

                # If save_path provided, save to disk
                if save_path:
                    # Determine format from extension
                    ext = os.path.splitext(save_path)[1].lower()
                    if ext in ['.png', '.gif', '.bmp']:
                        # Re-open original for lossless formats
                        with PILImage.open(tmp_path) as orig:
                            orig.save(save_path)
                    else:
                        # Save as JPEG for .jpg/.jpeg or unknown
                        with open(save_path, 'wb') as f:
                            f.write(jpeg_data)

                return Image(data=jpeg_data, format="jpeg")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def execute_js(self, script: str) -> str:
        """Execute JavaScript code on the page and return the result.

        IMPORTANT: Do NOT use 'return' statements directly in your script.
        The script is automatically wrapped to capture the result.

        Examples:
            Good: document.title
            Good: (function() { const x = 1 + 1; return x; })()
            Bad:  return document.title  // SyntaxError!

        For complex scripts, wrap in an IIFE:
            (function() {
                const data = [];
                // ... your code ...
                return data;
            })()
        """
        # check for common mistakes
        stripped = script.strip()
        if stripped.startswith('return ') and '(' not in stripped[:20]:
            return (
                "Error: Cannot use bare 'return' statement. "
                "Either remove 'return' (for simple expressions) or wrap in an IIFE: "
                "(function() { " + script + " })()"
            )

        try:
            result = await self.run_js(script)
            if result is None:
                return "(no return value)"
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            error_msg = str(e)
            # provide helpful error messages
            if 'SyntaxError' in error_msg and 'return' in script.lower():
                return (
                    f"SyntaxError: Illegal return statement. "
                    f"Wrap your code in an IIFE: (function() {{ {script} }})()"
                )
            return f"JavaScript Error: {error_msg}"

    async def wait(self, seconds: float = 1.0) -> str:
        """Wait for specified seconds."""
        await self.session.page.wait(seconds)
        return f"Waited {seconds}s"

    async def wait_for_element(self, selector: str, timeout: float = 30.0, visible: bool = True) -> str:
        """Wait for an element to appear on the page.

        Args:
            selector: CSS selector to wait for
            timeout: Maximum time to wait in seconds (default: 30s for SPAs)
            visible: If True, also checks element is visible (not hidden)
        """
        safe_sel = self.escape_js_string(selector)

        async def check():
            try:
                # use short timeout to avoid blocking
                elem = await self.session.page.select(selector, timeout=0.5)
                if elem is None:
                    return False
                if visible:
                    # also check visibility
                    is_visible = await self.run_js(f'''
                        (function() {{
                            const el = document.querySelector("{safe_sel}");
                            if (!el) return false;
                            const style = window.getComputedStyle(el);
                            return style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0";
                        }})()
                    ''')
                    return is_visible
                return True
            except Exception:
                return False

        if await self.wait_for_condition(check, timeout):
            return f"Element found: {selector}"

        # provide helpful suggestions on timeout
        suggestions = await self.run_js(f'''
            (function() {{
                const exact = document.querySelector("{safe_sel}");
                if (exact) {{
                    const style = window.getComputedStyle(exact);
                    if (style.display === "none") return "Element exists but has display:none";
                    if (style.visibility === "hidden") return "Element exists but has visibility:hidden";
                }}
                const all = document.querySelectorAll("*");
                const suggestions = [];
                for (const el of all) {{
                    if (el.id && el.id.toLowerCase().includes("{safe_sel}".toLowerCase().replace(/[#.\\[\\]]/g, ""))) {{
                        suggestions.push("#" + el.id);
                    }}
                }}
                return suggestions.length ? "Try: " + suggestions.slice(0, 3).join(", ") : null;
            }})()
        ''')

        hint = f" ({suggestions})" if suggestions else ""
        return f"Timeout: Element not found after {timeout}s: {selector}{hint}"

    async def run_security_audit(self) -> str:
        """Run a comprehensive security audit on the current page.

        Checks for: HTTPS, CSRF protection, password security, mixed content,
        inline scripts, SRI (Subresource Integrity), forms, sensitive data exposure,
        and JavaScript security patterns.
        """
        page = self.session.page
        url = getattr(page, "url", "unknown")

        lines = [
            "=" * 60,
            "SECURITY AUDIT REPORT",
            "=" * 60,
            f"URL: {url}",
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60, ""
        ]

        # https check
        is_https = url.startswith('https://')
        status = "PASS" if is_https else "FAIL"
        lines.append(f"[{status}] HTTPS: {self.bool_to_yes_no(is_https)}" + ("" if is_https else " - INSECURE"))

        # form security check
        forms_result = await self.run_js('''
            (function() {
                const forms = document.forms;
                let hasCSRF = false, hasInsecurePassword = false, formCount = forms.length;
                let passwordForms = 0;
                for (let form of forms) {
                    if (form.querySelector('input[name*="csrf"], input[name*="token"], input[name="_token"]')) hasCSRF = true;
                    if (form.querySelector('input[type="password"]')) {
                        passwordForms++;
                        if (form.method.toLowerCase() === 'get') hasInsecurePassword = true;
                    }
                }
                return { count: formCount, hasCSRF, hasInsecurePassword, passwordForms };
            })()
        ''')

        csrf_status = "WARN" if forms_result['count'] > 0 and not forms_result['hasCSRF'] else "PASS"
        lines.append(f"[{csrf_status}] CSRF Protection: {'Detected' if forms_result['hasCSRF'] else 'Not detected'}")

        pwd_status = "FAIL" if forms_result['hasInsecurePassword'] else "PASS"
        lines.append(f"[{pwd_status}] Password Security: {'INSECURE - GET method' if forms_result['hasInsecurePassword'] else 'OK'}")
        lines.append(f"[INFO] Forms: {forms_result['count']} total, {forms_result['passwordForms']} with passwords")

        # mixed content check
        mixed = await self.run_js('''
            (function() {
                if (location.protocol !== 'https:') return { check: false };
                const httpScripts = Array.from(document.scripts).filter(s => s.src?.startsWith('http://')).length;
                const httpStyles = Array.from(document.styleSheets).filter(s => s.href?.startsWith('http://')).length;
                const httpImages = Array.from(document.images).filter(i => i.src?.startsWith('http://')).length;
                return { check: true, scripts: httpScripts, styles: httpStyles, images: httpImages,
                         total: httpScripts + httpStyles + httpImages };
            })()
        ''')

        if mixed['check']:
            mixed_status = "FAIL" if mixed['total'] > 0 else "PASS"
            if mixed['total'] > 0:
                lines.append(f"[{mixed_status}] Mixed Content: {mixed['scripts']} scripts, {mixed['styles']} styles, {mixed['images']} images over HTTP")
            else:
                lines.append(f"[{mixed_status}] Mixed Content: None")

        # inline scripts check
        inline = await self.run_js('document.querySelectorAll("script:not([src])").length')
        inline_status = "INFO" if inline > 5 else "PASS"
        lines.append(f"[{inline_status}] Inline Scripts: {inline}")

        # sri check
        no_integrity = await self.run_js('Array.from(document.scripts).filter(s => s.src && !s.integrity).length')
        sri_status = "WARN" if no_integrity > 0 else "PASS"
        lines.append(f"[{sri_status}] Scripts without SRI: {no_integrity}")

        # external resources
        external = await self.run_js('''
            (function() {
                const currentHost = location.hostname;
                const getHost = url => { try { return new URL(url).hostname; } catch { return null; } };
                const scripts = Array.from(document.scripts).filter(s => s.src && getHost(s.src) !== currentHost).length;
                const iframes = Array.from(document.querySelectorAll('iframe')).filter(f => f.src && getHost(f.src) !== currentHost).length;
                return { scripts, iframes };
            })()
        ''')
        ext_status = "INFO" if external['scripts'] > 0 else "PASS"
        lines.append(f"[{ext_status}] External Scripts: {external['scripts']}, External Iframes: {external['iframes']}")

        # dangerous js patterns
        dangerous = await self.run_js('''
            (function() {
                const scripts = Array.from(document.scripts).map(s => s.innerHTML).join('\\n');
                return {
                    eval: (scripts.match(/eval\\s*\\(/g) || []).length,
                    innerHTML: (scripts.match(/\\.innerHTML\\s*=/g) || []).length,
                    documentWrite: (scripts.match(/document\\.write\\s*\\(/g) || []).length
                };
            })()
        ''')

        dangerous_total = dangerous['eval'] + dangerous['innerHTML'] + dangerous['documentWrite']
        js_status = "WARN" if dangerous_total > 0 else "PASS"
        if dangerous_total > 0:
            lines.append(f"[{js_status}] Dangerous JS Patterns: eval({dangerous['eval']}), innerHTML({dangerous['innerHTML']}), document.write({dangerous['documentWrite']})")
        else:
            lines.append(f"[{js_status}] Dangerous JS Patterns: None detected")

        # sensitive data scan
        sensitive = await self.run_js('''
            (function() {
                const html = document.documentElement.outerHTML;
                return {
                    awsKeys: (html.match(/AKIA[0-9A-Z]{16}/g) || []).length,
                    jwtTokens: (html.match(/eyJ[a-zA-Z0-9_-]*\\.eyJ[a-zA-Z0-9_-]*\\.[a-zA-Z0-9_-]*/g) || []).length,
                    privateKeys: (html.match(/-----BEGIN (RSA |EC |DSA |)PRIVATE KEY-----/g) || []).length
                };
            })()
        ''')

        sensitive_total = sensitive['awsKeys'] + sensitive['jwtTokens'] + sensitive['privateKeys']
        sens_status = "FAIL" if sensitive_total > 0 else "PASS"
        if sensitive_total > 0:
            lines.append(f"[{sens_status}] Exposed Secrets: AWS keys({sensitive['awsKeys']}), JWT tokens({sensitive['jwtTokens']}), Private keys({sensitive['privateKeys']})")
        else:
            lines.append(f"[{sens_status}] Exposed Secrets: None detected")

        lines.extend(["", "=" * 60])

        # summary
        checks = lines[7:]
        fails = sum(1 for line in checks if line.startswith('[FAIL]'))
        warns = sum(1 for line in checks if line.startswith('[WARN]'))
        passes = sum(1 for line in checks if line.startswith('[PASS]'))

        if fails > 0:
            lines.append(f"RESULT: {fails} CRITICAL, {warns} WARNINGS, {passes} PASSED")
        elif warns > 0:
            lines.append(f"RESULT: {warns} WARNINGS, {passes} PASSED")
        else:
            lines.append(f"RESULT: ALL {passes} CHECKS PASSED")

        return "\n".join(lines)
