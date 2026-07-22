# Token usage optimization

Date: 2026-07-22
Status: approved

## Context

Zendriver-mcp is structurally the largest token consumer in the author's Claude usage. Measurements on current main:

- The server registers 98 tools totalling ~43.5 KB of schema JSON (roughly 12-15k tokens). The `zendriver` server is registered globally in `~/.claude.json`, so these schemas load in every session of every project. In this repo `zendriver-dev` (from `.mcp.json`) loads on top of that, doubling the cost here.
- Largest single schemas: `click` (1085 B), `click_shadow` (981 B), `run_lighthouse` / `human_click` (968 B), `get_accessibility_snapshot` (894 B).
- Response side: `get_content` truncates at 50,000 chars (~12k tokens per call), `get_text_content` at 30,000. `get_interaction_tree` serializes with `indent=2`. `screenshot` returns full-viewport JPEG at quality 60 with no downscaling; vision tokens scale with pixel area.

Decision constraint: the global registration of `zendriver` stays (user preference). Optimization therefore happens server-side. The only config change is removing the duplicate load inside this repo (disable the global `zendriver` instance for this project so only `zendriver-dev` loads here).

Prior art: Anthropic's Tool Search / deferred loading mitigates schema cost in Claude Code, but tool names still load, other clients load everything, and response payloads are unaffected. Industry guidance (The New Stack, Atlassian, AWS) converges on <15-20 tools per server and summary-first responses.

## Part 1: Response diet (non-breaking, next release)

- `get_content(max_chars: int = 10000, offset: int = 0)`. Returns the requested slice and reports total available length so the agent can paginate deliberately. Previous behavior (50k chars) reachable by passing a larger `max_chars`.
- `get_text_content(max_chars: int = 10000, offset: int = 0)`, same pattern (was 30k fixed).
- `get_interaction_tree`: compact JSON serialization (`separators=(",", ":")`, no `indent=2`) plus a node cap parameter (`limit: int = 150`) with a note in the response when the cap was hit.
- `screenshot`: downscale to max 1024 px width (preserving aspect ratio) before JPEG encoding at quality 60. New parameter `full_resolution: bool = False` skips the downscale. Files saved via `save_path` keep original resolution.
- `get_network_logs` / `get_console_logs`: compact one-line-per-entry format with only the fields that matter (network: method, status, resource type, truncated URL; console: level, truncated message). Default `limit` drops from 50 to 20.

All changes are backwards compatible: existing call signatures keep working, only defaults get leaner.

## Part 2: Tool consolidation (v0.4, breaking)

Multiplex tool families behind an `action` parameter:

| New tool | Replaces | Count |
|---|---|---|
| `cookies` | get_cookies, set_cookie, clear_all_cookies, list_all_cookies, export_cookies, import_cookies | 6 -> 1 |
| `storage` | get_local_storage, set_local_storage, clear_storage | 3 -> 1 |
| `emulate` | set_user_agent, clear_user_agent, set_viewport, restore_viewport, set_device, list_devices, set_timezone, set_locale, set_geolocation, emulate_media, set_cpu_throttle, set_network_conditions, list_network_profiles | 13 -> 1 |
| `proxy` | configure_proxy, clear_proxy | 2 -> 1 |
| `permissions` | grant_permissions, reset_permissions, list_permission_names | 3 -> 1 |
| `screencast` | start_screencast, stop_screencast, export_screencast_mp4, check_ffmpeg_available | 4 -> 1 |
| `tabs` | new_tab, close_tab, switch_tab, list_tabs | 4 -> 1 |
| `intercept` | block_urls, unblock_all_urls, mock_response, fail_requests, list_interceptions, stop_interception, bypass_service_worker | 7 -> 1 |
| `logs` | get_network_logs, get_console_logs, clear_logs | 3 -> 1 |

Hot-path tools keep their own name and schema for model recognizability: `navigate`, `click`, `human_click`, `type_text`, `human_type`, `screenshot`, `find_element`, `get_interaction_tree`, `get_content`, `execute_js`, `wait_for_element`, and similar high-frequency tools.

Alongside consolidation, docstrings get trimmed: examples and long prose move to INSTRUCTIONS.md or are dropped; each description states what the tool does and its parameters, nothing more. Target end state is roughly 30 tools and a 60-70% reduction in schema bytes.

Also flagged for this pass: `execute_js` (verbose Examples block in its docstring and `json.dumps(result, indent=2)` pretty-printing every result) and `run_security_audit`'s `"="*60` banner lines.

## Error handling

- Multiplexed tools validate `action` against an enum; an invalid action returns an error listing the valid actions.
- `max_chars` and `offset` are clamped to sane bounds (`max_chars` >= 1, `offset` >= 0); out-of-range values clamp rather than error.

## Testing

- Update existing tests for the new defaults (content truncation, log limits).
- New tests: pagination behavior of `get_content` (slice + total length), screenshot output dimensions with and without `full_resolution`, compact log format.
- Guardrail: a test that dumps the full tool list (as in `scripts/`-style introspection) and fails when total schema JSON exceeds a byte budget, so schema bloat cannot silently return. Budget set after Part 1 lands (interim: 45 KB), tightened after Part 2 (target: 20 KB).

## Out of scope

- Removing the global registration (explicitly declined).
- Client-side mitigations (Tool Search / deferred loading) - already active in Claude Code, nothing to build.
