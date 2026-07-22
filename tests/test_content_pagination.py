"""Pagination + compact-tree behavior of the content tools."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from src.tools.content import ContentTools


def _tools_with_page(stub_mcp: Any, **page_attrs: Any) -> ContentTools:
    tools = ContentTools(stub_mcp)
    tools.session._page = SimpleNamespace(**page_attrs)  # type: ignore[attr-defined]
    return tools


async def test_get_content_default_slice_reports_total(stub_mcp: Any) -> None:
    tools = _tools_with_page(stub_mcp, get_content=AsyncMock(return_value="x" * 25000))
    out = await tools.get_content()
    assert out.startswith("[chars 0-10000 of 25000] (next: offset=10000)")
    body = out.split("\n", 1)[1]
    assert len(body) == 10000


async def test_get_content_offset_reaches_tail_without_next_hint(stub_mcp: Any) -> None:
    tools = _tools_with_page(stub_mcp, get_content=AsyncMock(return_value="abcdefghij" * 1000))
    out = await tools.get_content(max_chars=4000, offset=8000)
    assert out.startswith("[chars 8000-10000 of 10000]")
    assert "next:" not in out


async def test_get_content_clamps_bad_params(stub_mcp: Any) -> None:
    tools = _tools_with_page(stub_mcp, get_content=AsyncMock(return_value="hello"))
    out = await tools.get_content(max_chars=0, offset=-5)
    assert out.startswith("[chars 0-1 of 5]")


async def test_get_text_content_paginates_via_evaluate(stub_mcp: Any) -> None:
    tools = _tools_with_page(stub_mcp, evaluate=AsyncMock(return_value="t" * 12000))
    out = await tools.get_text_content()
    assert out.startswith("[chars 0-10000 of 12000] (next: offset=10000)")


async def test_interaction_tree_is_compact_and_capped(stub_mcp: Any) -> None:
    elements = [{"id": i, "t": "btn", "l": f"b{i}"} for i in range(200)]
    tools = _tools_with_page(stub_mcp, evaluate=AsyncMock(return_value=elements))
    out = await tools.get_interaction_tree()
    assert out.startswith("[showing 150 of 200 elements; raise limit for more]")
    payload = out.split("\n", 1)[1]
    assert '"id":149' in payload
    assert '"id":150' not in payload
    assert ": " not in payload  # separators=(",", ":") means no pretty-print spacing


async def test_interaction_tree_no_banner_under_limit(stub_mcp: Any) -> None:
    elements = [{"id": 0, "t": "btn", "l": "ok"}]
    tools = _tools_with_page(stub_mcp, evaluate=AsyncMock(return_value=elements))
    out = await tools.get_interaction_tree()
    assert out.startswith("[{")


async def test_get_content_offset_past_end_clamps_to_total(stub_mcp: Any) -> None:
    tools = _tools_with_page(stub_mcp, get_content=AsyncMock(return_value="x" * 100))
    out = await tools.get_content(offset=500)
    assert out.startswith("[chars 100-100 of 100]")
    assert "next:" not in out


async def test_get_content_empty_page(stub_mcp: Any) -> None:
    tools = _tools_with_page(stub_mcp, get_content=AsyncMock(return_value=""))
    out = await tools.get_content()
    assert out == "[chars 0-0 of 0]\n"
