"""
Unit and integration tests for the Playwright capture session and login automation.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import sys
import threading
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CAPTURE_PKG_DIR = os.path.join(PROJECT_ROOT, "packages", "capture")
if CAPTURE_PKG_DIR not in sys.path:
    sys.path.insert(0, CAPTURE_PKG_DIR)

from session import BrowserSession, perform_login


class MockLoginServer(BaseHTTPRequestHandler):
    """Local HTTP server providing test login form and dashboard endpoint."""

    def do_GET(self):
        if self.path == "/login":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <!DOCTYPE html>
                <html>
                <head><title>Test Login</title></head>
                <body>
                    <form action="/login" method="POST">
                        <input id="username" name="username" type="text" />
                        <input id="password" name="password" type="password" />
                        <button id="submit-btn" type="submit">Sign In</button>
                    </form>
                </body>
                </html>
            """)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/login":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()

            if "username=admin" in body and "password=secret123" in body:
                self.wfile.write(b"""
                    <!DOCTYPE html>
                    <html>
                    <body>
                        <div id="dashboard"><h1>Welcome to Dashboard</h1></div>
                    </body>
                    </html>
                """)
            else:
                self.wfile.write(b"""
                    <!DOCTYPE html>
                    <html>
                    <body>
                        <div id="login-error">Invalid credentials</div>
                    </body>
                    </html>
                """)

    def log_message(self, format, *args):
        """Silence HTTP request logs during testing."""
        pass


class TestBrowserSessionAndLogin(unittest.TestCase):
    """Test suite verifying Playwright browser session management and login automation."""

    @classmethod
    def setUpClass(cls):
        """Start local HTTP server on random available port."""
        cls.server = HTTPServer(("127.0.0.1", 0), MockLoginServer)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        """Shutdown local HTTP server."""
        cls.server.shutdown()
        cls.server.server_close()

    def test_browser_session_lifecycle(self):
        """BrowserSession starts and closes cleanly using context manager."""
        session = BrowserSession(headless=True)
        with session as page:
            self.assertIsNotNone(page)
            page.goto(f"{self.base_url}/login")
            title = page.title()
            self.assertEqual(title, "Test Login")
        self.assertIsNone(session.page)

    def test_successful_login(self):
        """perform_login navigates, enters credentials, submits, and finds success element."""
        with BrowserSession(headless=True) as page:
            login_result = perform_login(
                page=page,
                login_url=f"{self.base_url}/login",
                username_selector="#username",
                username="admin",
                password_selector="#password",
                password="secret123",
                submit_selector="#submit-btn",
                success_indicator_selector="#dashboard",
                timeout_ms=5000,
            )
            self.assertTrue(login_result)
            dashboard_text = page.text_content("#dashboard")
            self.assertIn("Welcome to Dashboard", dashboard_text or "")


if __name__ == "__main__":
    unittest.main()
