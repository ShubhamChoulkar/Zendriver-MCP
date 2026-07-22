# Token Usage Optimization Part 1 (Response Diet) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shrink the token cost of zendriver-mcp's high-frequency tool responses (page content, interaction tree, screenshots, logs) without breaking any existing call, and add a schema-size guardrail test.

**Architecture:** Four independent server-side changes in existing tool modules (`content.py`, `utils.py`, `logging.py`) plus one new registry-introspection test. All changes only tighten defaults and add optional parameters; signatures stay backwards compatible. Spec: `docs/superpowers/specs/2026-07-22-token-usage-optimization-design.md` (this plan covers Part 1 + the guardrail; Part 2 tool consolidation gets its own plan for v0.4).

**Tech Stack:** Python >=3.10, `mcp` SDK >=1.0 (FastMCP), Pillow (unpinned, assume >=10: use `Image.Resampling.LANCZOS`), pytest >=8 with pytest-asyncio in `asyncio_mode = "auto"` (async tests need no marker), ruff.

**Required Skills:** none (no Python/FastMCP best-practices skill available in this roster).

**Flow:** speed-mode (parallel waves, commit per wave)

**Repo conventions the implementer must know:**
- Tools are methods on `ToolBase` subclasses, registered via `self._register(self.method)` (`src/tools/base.py:64`). FastMCP derives the schema from the method signature and docstring, so keep docstrings short: every docstring byte is context-window cost in every client session.
- Tests mock the browser by assigning `tools.session._page = <fake>` after constructing the tool class with the `stub_mcp` fixture from `tests/conftest.py` (see `tests/test_accessibility_render.py:73` for the pattern).
- The working tree has unrelated uncommitted edits in `CHANGELOG.md`, `src/tools/_shadow_js.py`, and `src/tools/elements.py`. Never revert or stage those files except where a task explicitly says to edit `CHANGELOG.md` (append-only there).

---

## Dependency Graph

- Task 1: (none)
- Task 2: (none)
- Task 3: (none)
- Task 4: (none)
- Task 5: blockedBy [Task 1, Task 2, Task 3, Task 4]

## Shared Infrastructure

- `CHANGELOG.md` (has unrelated uncommitted edits; only Task 5 touches it, solo wave, append-only)
- `pyproject.toml`, `uv.lock` (no task may touch these)
- `tests/conftest.py` (no task may touch it)

## Waves

### Wave 1 (parallel: 4 tasks)
- Task 1: Content pagination + compact interaction tree
- Task 2: Screenshot downscale
- Task 3: Leaner log defaults
- Task 4: Schema budget guardrail test

### Wave 2 (solo — touches CHANGELOG.md)
- Task 5: Changelog entry

---

### Task 1: Content pagination + compact interaction tree

**Files:**
- Modify: `src/tools/content.py:16-47`
- Test: `tests/test_content_pagination.py` (create)

**Wave:** 1

- [ ] **Step 1: Write test + implementation**

Test (`tests/test_content_pagination.py`):

```python
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
```

Implementation — replace `get_content`, `get_text_content`, and `get_interaction_tree` in `src/tools/content.py` (keep `scroll` / `scroll_to_element` and the imports untouched, and add the `_paginate` helper):

```python
    async def get_content(self, max_chars: int = 10000, offset: int = 0) -> str:
        """Get the page HTML, ``max_chars`` chars from ``offset``.

        The first line reports the slice, total size, and the next offset
        when more content is available.
        """
        content = await self.session.page.get_content()
        return self._paginate(content, max_chars, offset)

    async def get_text_content(self, max_chars: int = 10000, offset: int = 0) -> str:
        """Get visible page text; same pagination contract as get_content."""
        text = await self.run_js("document.body.innerText")
        return self._paginate(str(text), max_chars, offset)

    @staticmethod
    def _paginate(text: str, max_chars: int, offset: int) -> str:
        """Slice ``text`` with a one-line header so agents can paginate."""
        max_chars = max(1, max_chars)
        offset = max(0, offset)
        total = len(text)
        chunk = text[offset : offset + max_chars]
        end = offset + len(chunk)
        header = f"[chars {offset}-{end} of {total}]"
        if end < total:
            header += f" (next: offset={end})"
        return f"{header}\n{chunk}"

    async def get_interaction_tree(self, limit: int = 150) -> str:
        """List interactive elements as compact JSON with numeric ids.

        The ids double as selectors for click/type tools. ``limit`` caps
        the element count.
        """
        import json
        import os

        script_path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "dom_walker.js")
        if not os.path.exists(script_path):
            return "Error: dom_walker.js not found in static/js"

        with open(script_path, encoding="utf-8") as f:
            js_code = f.read()

        try:
            tree = await self.run_js(js_code)
        except Exception as e:
            return f"Error analyzing page: {str(e)}"

        tree = tree or []
        limit = max(1, limit)
        total = len(tree)
        payload = json.dumps(tree[:limit], separators=(",", ":"))
        if total > limit:
            return f"[showing {limit} of {total} elements; raise limit for more]\n{payload}"
        return payload
```

⚠ Keep the docstrings exactly this terse. They feed the tool schema; do not add examples or prose.

- [ ] **Step 2: Run tests to verify pass**

Run: `uv run pytest tests/test_content_pagination.py -q`
Expected: 6 passed

- [ ] **Step 3: Stage declared files**

```bash
git add src/tools/content.py tests/test_content_pagination.py
```

⚠ Do NOT use `git add -A` or `git add .`. Do NOT commit — the controller commits at wave boundary.

---

### Task 2: Screenshot downscale

**Files:**
- Modify: `src/tools/utils.py:26-72`
- Test: `tests/test_screenshot_downscale.py` (create)

**Wave:** 1

- [ ] **Step 1: Write test + implementation**

Test (`tests/test_screenshot_downscale.py`):

```python
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
```

⚠ `resolve_artifact_path` sandboxes writes to `$HOME` / tempdir / `$ZENDRIVER_MCP_ARTIFACT_ROOT`; pytest's `tmp_path` lives under the system tempdir, so it passes the sandbox.

Implementation — in `src/tools/utils.py`, add a module-level constant under the imports and replace the `screenshot` method. The `if not self.session.page:` placeholder branch stays exactly as it is (changing its semantics is out of scope).

```python
MAX_SCREENSHOT_WIDTH = 1024
```

```python
    async def screenshot(self, save_path: str | None = None, full_resolution: bool = False) -> Image:
        """Screenshot the page as JPEG, downscaled to max 1024px wide.

        Args:
            save_path: Optional path to also save to disk at full
                resolution (format from the extension).
            full_resolution: Return the image without downscaling.
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
                rgb = img.convert("RGB")
                full_res = rgb
                if not full_resolution and rgb.width > MAX_SCREENSHOT_WIDTH:
                    new_height = round(rgb.height * MAX_SCREENSHOT_WIDTH / rgb.width)
                    rgb = rgb.resize(
                        (MAX_SCREENSHOT_WIDTH, new_height), PILImage.Resampling.LANCZOS
                    )
                buffer = io.BytesIO()
                rgb.save(buffer, format="JPEG", quality=60, optimize=True)
                jpeg_data = buffer.getvalue()

                # If save_path provided, resolve through the sandbox then
                # pick the format from the extension. Saved files keep the
                # original resolution; only the returned image is downscaled.
                if save_path:
                    ext = os.path.splitext(save_path)[1].lower()
                    default_ext = "png" if ext in {".png", ".gif", ".bmp"} else "jpg"
                    resolved = resolve_artifact_path(
                        save_path,
                        default_prefix="zendriver-screenshot",
                        default_ext=default_ext,
                    )
                    if ext in [".png", ".gif", ".bmp"]:
                        with PILImage.open(tmp_path) as orig:
                            orig.save(str(resolved))
                    else:
                        full_buffer = io.BytesIO()
                        full_res.save(full_buffer, format="JPEG", quality=60, optimize=True)
                        resolved.write_bytes(full_buffer.getvalue())

                return Image(data=jpeg_data, format="jpeg")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
```

⚠ Use `resize`, not `thumbnail` (`thumbnail` mutates in place and returns None). Use `PILImage.Resampling.LANCZOS`; the bare `PILImage.LANCZOS` alias is deprecated territory across Pillow 10/11.

- [ ] **Step 2: Run tests to verify pass**

Run: `uv run pytest tests/test_screenshot_downscale.py -q`
Expected: 4 passed

- [ ] **Step 3: Stage declared files**

```bash
git add src/tools/utils.py tests/test_screenshot_downscale.py
```

⚠ Do NOT use `git add -A` or `git add .`. Do NOT commit — the controller commits at wave boundary.

---

### Task 3: Leaner log defaults

**Files:**
- Modify: `src/tools/logging.py:18-43`
- Test: `tests/test_log_limits.py` (create)

**Wave:** 1

- [ ] **Step 1: Write test + implementation**

Test (`tests/test_log_limits.py`):

```python
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
```

Implementation — replace `get_network_logs` and `get_console_logs` in `src/tools/logging.py` (leave `clear_logs`, `wait_for_network`, `wait_for_request` untouched):

```python
    async def get_network_logs(self, limit: int = 20) -> str:
        """Get recent network request logs captured via CDP."""
        logs = self.session.get_network_logs(limit)
        if not logs:
            return "No network logs captured"

        lines = [f"Network logs ({len(logs)} entries):"]
        for log in logs:
            method = log.get("method", "GET")
            url = log.get("url", "unknown")[:80]
            status = log.get("status", "?")
            rtype = log.get("type", "")
            lines.append(f"  {method} {url} {status} {rtype}".rstrip())
        return "\n".join(lines)

    async def get_console_logs(self, limit: int = 20) -> str:
        """Get recent console logs captured via CDP."""
        logs = self.session.get_console_logs(limit)
        if not logs:
            return "No console logs captured"

        lines = [f"Console logs ({len(logs)} entries):"]
        for log in logs:
            log_type = log.get("type", "log")
            text = log.get("text", "")[:100]
            lines.append(f"  [{log_type}] {text}")
        return "\n".join(lines)
```

- [ ] **Step 2: Run tests to verify pass**

Run: `uv run pytest tests/test_log_limits.py -q`
Expected: 2 passed

- [ ] **Step 3: Stage declared files**

```bash
git add src/tools/logging.py tests/test_log_limits.py
```

⚠ Do NOT use `git add -A` or `git add .`. Do NOT commit — the controller commits at wave boundary.

---

### Task 4: Schema budget guardrail test

**Files:**
- Test: `tests/test_schema_budget.py` (create)

**Wave:** 1

- [ ] **Step 1: Write test + implementation**

There is no implementation change; the test IS the deliverable. It introspects the live registry the same way `tests/test_timeouts.py` does, via the module-level `mcp` in `src/tools/__init__.py`.

```python
"""Guardrail: total tool schema size must stay under budget.

Tool schemas load into every client session's context window. Current
main measures ~43.5 KB across 98 tools; the interim budget is 45 KB.
After the v0.4 consolidation (Part 2 of the 2026-07-22 token spec)
tighten BUDGET_BYTES to 20_000. If this test fails, trim docstrings or
consolidate tools — do NOT raise the budget.
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
```

⚠ Wave 1's other tasks add a few parameters (schema grows slightly); 45 KB accommodates that. If this fails at the wave boundary, the fix is trimming the docstrings touched in Tasks 1-3.

- [ ] **Step 2: Run tests to verify pass**

Run: `uv run pytest tests/test_schema_budget.py -q`
Expected: 1 passed

- [ ] **Step 3: Stage declared files**

```bash
git add tests/test_schema_budget.py
```

⚠ Do NOT use `git add -A` or `git add .`. Do NOT commit — the controller commits at wave boundary.

---

### Task 5: Changelog entry

**Files:**
- Modify: `CHANGELOG.md` (top, under `## [Unreleased]`)

**Wave:** 2 (solo)

- [ ] **Step 1: Append changelog bullets**

⚠ `CHANGELOG.md` already contains unrelated uncommitted edits under `## [Unreleased]` (click/CDP work). Append to the existing `### Changed` list and add an `### Added` subsection if one is missing. Do not reorder, rewrite, or delete anything that is already there.

Add to the existing `### Changed` section under `## [Unreleased]`:

```markdown
- `get_content` / `get_text_content` default to 10,000 chars and take
  `max_chars` + `offset`; the first line reports the total size and the
  next offset so agents can paginate instead of swallowing 50k chars.
- `get_interaction_tree` emits compact JSON (no pretty-printing) and
  caps output at 150 elements via a new `limit` parameter.
- `screenshot` downscales to max 1024px wide before JPEG encoding
  (vision tokens scale with pixel area); pass `full_resolution=true`
  for the old behavior. Files written via `save_path` keep full
  resolution.
- Network/console log tools default to 20 entries (was 50); network
  lines now include the resource type.
```

Add (or extend) an `### Added` subsection under `## [Unreleased]`:

```markdown
### Added
- Schema budget guardrail (`tests/test_schema_budget.py`): fails CI
  when total tool schema JSON exceeds 45 KB, so schema bloat cannot
  silently return.
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -q`
Expected: all tests pass, no failures

- [ ] **Step 3: Stage declared files**

```bash
git add CHANGELOG.md
```

⚠ Do NOT use `git add -A` or `git add .`. Do NOT commit — the controller commits at wave boundary.

---

## Wave-boundary checks (controller)

After each wave, before committing:

```bash
uv run pytest -q
uv run ruff format src tests && uv run ruff check src tests
```

Expected: full suite green, ruff clean. Commit messages: `Part 1 response diet: content pagination, screenshot downscale, log limits, schema budget` (wave 1) and `Changelog for response diet` (wave 2). No AI attribution lines in commit messages.

## Out of scope

- Part 2 tool consolidation (separate plan for v0.4).
- Version bump / release tagging.
- The `if not self.session.page:` placeholder branch in `screenshot` (latent behavior, unchanged).
