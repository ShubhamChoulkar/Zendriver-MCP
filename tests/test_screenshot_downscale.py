"""Screenshot downscaling: returned image caps at 1024px wide, files keep full res."""

from __future__ import annotations

import io
from types import SimpleNamespace
from typing import Any

from PIL import Image as PILImage

from src.tools.utils import MAX_SCREENSHOT_WIDTH, UtilityTools


def _tools_with_fake_screenshot(stub_mcp: Any, width: int, height: int) -> UtilityTools:
    async def fake_save_screenshot(path: str) -> None:
        PILImage.new("RGB", (width, height), color=(10, 120, 200)).save(path, format="PNG")

    tools = UtilityTools(stub_mcp)
    tools.session._page = SimpleNamespace(save_screenshot=fake_save_screenshot)  # type: ignore[attr-defined]
    return tools


def _decode(result: Any) -> PILImage.Image:
    return PILImage.open(io.BytesIO(result.data))


async def test_wide_screenshot_downscales_to_max_width(stub_mcp: Any) -> None:
    tools = _tools_with_fake_screenshot(stub_mcp, 2048, 1200)
    img = _decode(await tools.screenshot())
    assert img.width == MAX_SCREENSHOT_WIDTH
    assert img.height == 600  # aspect ratio preserved


async def test_full_resolution_flag_skips_downscale(stub_mcp: Any) -> None:
    tools = _tools_with_fake_screenshot(stub_mcp, 2048, 1200)
    img = _decode(await tools.screenshot(full_resolution=True))
    assert img.width == 2048


async def test_small_screenshot_untouched(stub_mcp: Any) -> None:
    tools = _tools_with_fake_screenshot(stub_mcp, 800, 600)
    img = _decode(await tools.screenshot())
    assert img.width == 800


async def test_saved_jpeg_keeps_full_resolution(stub_mcp: Any, tmp_path: Any) -> None:
    tools = _tools_with_fake_screenshot(stub_mcp, 2048, 1200)
    target = tmp_path / "shot.jpg"
    returned = _decode(await tools.screenshot(save_path=str(target)))
    assert returned.width == MAX_SCREENSHOT_WIDTH
    with PILImage.open(target) as saved:
        assert saved.width == 2048
