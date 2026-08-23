"""
Playwright browser session and login automation for Web2Actions.
Handles browser lifecycle, navigation, and automated form authentication.
"""

from typing import Optional
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, Playwright


class BrowserSession:
    """Manages the lifecycle of a Playwright browser context and page."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def start(self) -> Page:
        """Start the browser and create a fresh context and page."""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context()
        self.page = self._context.new_page()
        return self.page

    def close(self):
        """Close page, context, browser, and stop Playwright cleanly."""
        if self._context is not None:
            self._context.close()
            self._context = None
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self.page = None

    def __enter__(self) -> Page:
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def perform_login(
    page: Page,
    login_url: str,
    username_selector: str,
    username: str,
    password_selector: str,
    password: str,
    submit_selector: str,
    success_indicator_selector: Optional[str] = None,
    timeout_ms: int = 10000,
) -> bool:
    """
    Navigate to login page, fill credentials, submit, and verify success indicator.
    Returns True if login succeeds.
    """
    page.goto(login_url, wait_until="domcontentloaded", timeout=timeout_ms)
    page.fill(username_selector, username, timeout=timeout_ms)
    page.fill(password_selector, password, timeout=timeout_ms)
    page.click(submit_selector, timeout=timeout_ms)

    if success_indicator_selector:
        page.wait_for_selector(success_indicator_selector, timeout=timeout_ms)

    return True
