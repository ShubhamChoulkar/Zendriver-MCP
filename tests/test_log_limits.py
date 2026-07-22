"""Log tools default to 20 entries and a compact line format."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from src.tools.logging import LoggingTools


async def test_network_logs_default_limit_and_format(stub_mcp: Any) -> None:
    tools = LoggingTools(stub_mcp)
    tools.session.get_network_logs = MagicMock(  # type: ignore[method-assign]
        return_value=[{"method": "GET", "url": "https://a.example/x", "status": 200, "type": "xhr"}]
    )
    out = await tools.get_network_logs()
    tools.session.get_network_logs.assert_called_once_with(20)
    assert "GET https://a.example/x 200 xhr" in out


async def test_console_logs_default_limit(stub_mcp: Any) -> None:
    tools = LoggingTools(stub_mcp)
    tools.session.get_console_logs = MagicMock(  # type: ignore[method-assign]
        return_value=[{"type": "error", "text": "boom"}]
    )
    out = await tools.get_console_logs()
    tools.session.get_console_logs.assert_called_once_with(20)
    assert "[error] boom" in out
