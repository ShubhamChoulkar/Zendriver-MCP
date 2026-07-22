"""Guardrail: total tool schema size must stay under budget.

Tool schemas load into every client session's context window. Current
main measures ~43.5 KB across 98 tools; the interim budget is 45 KB.
After the v0.4 consolidation (Part 2 of the 2026-07-22 token spec)
tighten BUDGET_BYTES to 20_000. If this test fails, trim docstrings or
consolidate tools - do NOT raise the budget.
"""

from __future__ import annotations

import json

from src.tools import mcp

BUDGET_BYTES = 45_000


async def test_total_schema_size_under_budget() -> None:
    tools = await mcp.list_tools()
    blob = json.dumps(
        [
            {"name": t.name, "description": t.description or "", "schema": t.inputSchema}
            for t in tools
        ]
    )
    assert len(blob) <= BUDGET_BYTES, (
        f"tool schemas total {len(blob)} bytes (budget {BUDGET_BYTES}); "
        "trim tool docstrings or consolidate tools instead of raising the budget"
    )
