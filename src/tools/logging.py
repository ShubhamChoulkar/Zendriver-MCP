# logging tools - network and console log management
import time
from typing import Optional

from src.tools.base import ToolBase


class LoggingTools(ToolBase):
    """tools for network and console log access"""

    def _register_tools(self) -> None:
        """register logging tools"""
        self._mcp.tool()(self.get_network_logs)
        self._mcp.tool()(self.get_console_logs)
        self._mcp.tool()(self.clear_logs)
        self._mcp.tool()(self.wait_for_network)
        self._mcp.tool()(self.wait_for_request)

    async def get_network_logs(self, limit: int = 50) -> str:
        """Get recent network request logs captured via CDP."""
        logs = self.session.get_network_logs(limit)
        if not logs:
            return "No network logs captured"

        lines = [f"Network logs ({len(logs)} entries):"]
        for log in logs:
            method = log.get('method', 'GET')
            url = log.get('url', 'unknown')[:80]
            status = log.get('status', '?')
            lines.append(f"  {method} {url} - {status}")
        return "\n".join(lines)

    async def get_console_logs(self, limit: int = 50) -> str:
        """Get recent console logs captured via CDP."""
        logs = self.session.get_console_logs(limit)
        if not logs:
            return "No console logs captured"

        lines = [f"Console logs ({len(logs)} entries):"]
        for log in logs:
            log_type = log.get('type', 'log')
            text = log.get('text', '')[:100]
            lines.append(f"  [{log_type}] {text}")
        return "\n".join(lines)

    async def clear_logs(self) -> str:
        """Clear all captured network and console logs."""
        self.session.clear_logs()
        return "Cleared all logs"

    async def wait_for_network(self, timeout: float = 10.0, idle_time: float = 0.5) -> str:
        """Wait for network activity to become idle.

        Useful after triggering actions that cause API calls.

        Args:
            timeout: Maximum time to wait in seconds
            idle_time: How long network must be idle to consider it done
        """
        start = time.time()
        last_count = 0
        idle_start = None

        while time.time() - start < timeout:
            logs = self.session.get_network_logs(100)
            current_count = len(logs)

            if current_count == last_count:
                # no new requests
                if idle_start is None:
                    idle_start = time.time()
                elif time.time() - idle_start >= idle_time:
                    # network has been idle long enough
                    elapsed = time.time() - start
                    return f"Network idle after {elapsed:.1f}s ({current_count} requests captured)"
            else:
                # new request came in, reset idle timer
                idle_start = None
                last_count = current_count

            await self.session.page.wait(0.1)

        return f"Timeout after {timeout}s - network may still be active ({last_count} requests captured)"

    async def wait_for_request(
        self,
        url_pattern: str,
        timeout: float = 30.0,
        method: Optional[str] = None
    ) -> str:
        """Wait for a specific network request to complete.

        Args:
            url_pattern: Substring to match in the URL (e.g., '/api/search', 'graphql')
            timeout: Maximum time to wait in seconds
            method: Optional HTTP method filter ('GET', 'POST', etc.)

        Returns info about the matching request when found.
        """
        start = time.time()
        seen_requests = set()
        safe_pattern = url_pattern.lower()
        safe_method = method.upper() if method else None

        while time.time() - start < timeout:
            logs = self.session.get_network_logs(200)

            for log in logs:
                # create unique id for this request
                req_id = f"{log.get('method', '')}:{log.get('url', '')}:{log.get('timestamp', '')}"
                if req_id in seen_requests:
                    continue
                seen_requests.add(req_id)

                url = log.get('url', '').lower()
                req_method = log.get('method', 'GET')

                # check if this request matches our pattern
                if safe_pattern in url:
                    if safe_method and req_method != safe_method:
                        continue

                    status = log.get('status', '?')
                    elapsed = time.time() - start
                    return (
                        f"Found matching request after {elapsed:.1f}s:\n"
                        f"  {req_method} {log.get('url', '')[:100]}\n"
                        f"  Status: {status}\n"
                        f"  Type: {log.get('type', 'unknown')}"
                    )

            await self.session.page.wait(0.2)

        return f"Timeout: No request matching '{url_pattern}' found after {timeout}s"
