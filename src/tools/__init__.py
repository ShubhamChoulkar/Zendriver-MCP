# tools package - modular browser automation tools for Zendriver MCP server
from mcp.server.fastmcp import FastMCP

from src.tools.base import ToolBase
from src.tools.browser import BrowserTools
from src.tools.navigation import NavigationTools
from src.tools.tabs import TabTools
from src.tools.elements import ElementTools
from src.tools.query import QueryTools
from src.tools.content import ContentTools
from src.tools.storage import StorageTools
from src.tools.logging import LoggingTools
from src.tools.forms import FormTools
from src.tools.utils import UtilityTools
from src.tools.recording import RecordingTools

# initialize the MCP server
mcp = FastMCP("Zendriver MCP")

# register all tool modules and keep instances for backwards compatibility
_browser_tools = BrowserTools(mcp)
_navigation_tools = NavigationTools(mcp)
_tab_tools = TabTools(mcp)
_element_tools = ElementTools(mcp)
_query_tools = QueryTools(mcp)
_content_tools = ContentTools(mcp)
_storage_tools = StorageTools(mcp)
_logging_tools = LoggingTools(mcp)
_form_tools = FormTools(mcp)
_utility_tools = UtilityTools(mcp)
_recording_tools = RecordingTools(mcp)

# export individual tool functions for backwards compatibility
# browser lifecycle
start_browser = _browser_tools.start_browser
stop_browser = _browser_tools.stop_browser
get_browser_status = _browser_tools.get_browser_status

# navigation
navigate = _navigation_tools.navigate
go_back = _navigation_tools.go_back
go_forward = _navigation_tools.go_forward
reload_page = _navigation_tools.reload_page
get_page_info = _navigation_tools.get_page_info

# tabs
new_tab = _tab_tools.new_tab
list_tabs = _tab_tools.list_tabs
switch_tab = _tab_tools.switch_tab
close_tab = _tab_tools.close_tab

# elements
click = _element_tools.click
type_text = _element_tools.type_text
clear_input = _element_tools.clear_input
focus_element = _element_tools.focus_element
select_option = _element_tools.select_option
upload_file = _element_tools.upload_file
highlight_element = _element_tools.highlight_element
hide_element = _element_tools.hide_element
remove_element = _element_tools.remove_element

# query
find_element = _query_tools.find_element
find_all_elements = _query_tools.find_all_elements
get_element_text = _query_tools.get_element_text
get_element_attribute = _query_tools.get_element_attribute
find_buttons = _query_tools.find_buttons
find_inputs = _query_tools.find_inputs

# content
get_content = _content_tools.get_content
get_text_content = _content_tools.get_text_content
get_interaction_tree = _content_tools.get_interaction_tree
get_links = _content_tools.get_links
extract_table = _content_tools.extract_table
extract_structured_data = _content_tools.extract_structured_data
scroll = _content_tools.scroll
scroll_to_element = _content_tools.scroll_to_element

# storage
get_cookies = _storage_tools.get_cookies
set_cookie = _storage_tools.set_cookie
get_local_storage = _storage_tools.get_local_storage
set_local_storage = _storage_tools.set_local_storage
clear_storage = _storage_tools.clear_storage

# logging
get_network_logs = _logging_tools.get_network_logs
get_console_logs = _logging_tools.get_console_logs
clear_logs = _logging_tools.clear_logs
wait_for_network = _logging_tools.wait_for_network
wait_for_request = _logging_tools.wait_for_request
get_network_response_body = _logging_tools.get_network_response_body

# forms
fill_form = _form_tools.fill_form
submit_form = _form_tools.submit_form
press_key = _form_tools.press_key
press_enter = _form_tools.press_enter
mouse_click = _form_tools.mouse_click

# utils
screenshot = _utility_tools.screenshot
screenshot_element = _utility_tools.screenshot_element
execute_js = _utility_tools.execute_js
wait = _utility_tools.wait
wait_for_element = _utility_tools.wait_for_element
wait_for_text = _utility_tools.wait_for_text
download_file = _utility_tools.download_file
run_security_audit = _utility_tools.run_security_audit

# recording
start_recording = _recording_tools.start_recording
stop_recording = _recording_tools.stop_recording
replay_action_sequence = _recording_tools.replay_action_sequence

__all__ = [
    # mcp server
    "mcp",
    # base class
    "ToolBase",
    # tool classes
    "BrowserTools",
    "NavigationTools",
    "TabTools",
    "ElementTools",
    "QueryTools",
    "ContentTools",
    "StorageTools",
    "LoggingTools",
    "FormTools",
    "UtilityTools",
    "RecordingTools",
    # individual tool functions
    "start_browser", "stop_browser", "get_browser_status",
    "navigate", "go_back", "go_forward", "reload_page", "get_page_info",
    "new_tab", "list_tabs", "switch_tab", "close_tab",
    "click", "type_text", "clear_input", "focus_element", "select_option", "upload_file",
    "highlight_element", "hide_element", "remove_element",
    "find_element", "find_all_elements", "get_element_text", "get_element_attribute",
    "find_buttons", "find_inputs",
    "get_content", "get_text_content", "get_interaction_tree", "get_links", "extract_table", "extract_structured_data", "scroll", "scroll_to_element",
    "get_cookies", "set_cookie", "get_local_storage", "set_local_storage", "clear_storage",
    "get_network_logs", "get_console_logs", "clear_logs", "wait_for_network", "wait_for_request", "get_network_response_body",
    "fill_form", "submit_form", "press_key", "press_enter", "mouse_click",
    "screenshot", "screenshot_element", "execute_js", "wait", "wait_for_element", "wait_for_text", "download_file", "run_security_audit",
    "start_recording", "stop_recording", "replay_action_sequence",
]
