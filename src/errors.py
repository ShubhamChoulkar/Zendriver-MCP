# custom exceptions for Zendriver MCP server


class ZendriverMCPError(Exception):
    # base exception for all Zendriver MCP errors
    pass


class BrowserNotStartedError(ZendriverMCPError):
    # raised when browser operations attempted before starting
    def __init__(self, message: str = "Browser not started. Call start_browser first."):
        super().__init__(message)


class PageNotLoadedError(ZendriverMCPError):
    # raised when page operations attempted before navigating
    def __init__(self, message: str = "No page loaded. Navigate to a URL first."):
        super().__init__(message)


class ElementNotFoundError(ZendriverMCPError):
    # raised when element cannot be found on the page
    def __init__(self, selector: str):
        super().__init__(f"Element not found: {selector}")
        self.selector = selector
