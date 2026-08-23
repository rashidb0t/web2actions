"""
Unit and integration tests for network traffic recording during browser interaction.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import sys
import threading
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CAPTURE_PKG_DIR = os.path.join(PROJECT_ROOT, "packages", "capture")
if CAPTURE_PKG_DIR not in sys.path:
    sys.path.insert(0, CAPTURE_PKG_DIR)

from session import BrowserSession, perform_login
from recorder import NetworkRecorder


class MockAppServer(BaseHTTPRequestHandler):
    """Mock application server simulating login and follow-up API endpoints."""

    def do_GET(self):
        if self.path == "/login":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <!DOCTYPE html>
                <html>
                <body>
                    <form action="/login" method="POST">
                        <input id="username" name="username" type="text" />
                        <input id="password" name="password" type="password" />
                        <button id="submit-btn" type="submit">Sign In</button>
                    </form>
                </body>
                </html>
            """)
        elif self.path == "/api/profile":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"user": "admin", "role": "lead"}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/login":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <!DOCTYPE html>
                <html>
                <body>
                    <div id="dashboard">Logged In</div>
                </body>
                </html>
            """)
        elif self.path == "/api/items":
            content_length = int(self.headers.get("Content-Length", 0))
            payload = self.rfile.read(content_length).decode("utf-8")
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "created", "echo": payload}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


class TestNetworkRecorder(unittest.TestCase):
    """Test suite verifying accurate network request and response capturing."""

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), MockAppServer)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_record_login_and_followup_requests(self):
        """Recorder captures login POST, subsequent GET /api/profile, and POST /api/items."""
        recorder = NetworkRecorder()

        with BrowserSession(headless=True) as page:
            recorder.start(page)

            # 1. Perform login
            perform_login(
                page=page,
                login_url=f"{self.base_url}/login",
                username_selector="#username",
                username="admin",
                password_selector="#password",
                password="secret123",
                submit_selector="#submit-btn",
                success_indicator_selector="#dashboard",
            )

            # 2. Perform follow-up actions (fetch profile and create item)
            page.evaluate(f"""
                async () => {{
                    await fetch('{self.base_url}/api/profile');
                    await fetch('{self.base_url}/api/items', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ name: 'Widget A', price: 42 }})
                    }});
                }}
            """)

            recorder.stop()

        entries = recorder.get_entries()
        self.assertGreaterEqual(len(entries), 3)

        # Verify POST /login was captured
        login_entries = [e for e in entries if "/login" in e["url"] and e["method"] == "POST"]
        self.assertEqual(len(login_entries), 1)
        self.assertEqual(login_entries[0]["response_status"], 200)

        # Verify GET /api/profile was captured
        profile_entries = [e for e in entries if "/api/profile" in e["url"]]
        self.assertEqual(len(profile_entries), 1)
        self.assertEqual(profile_entries[0]["method"], "GET")
        self.assertEqual(profile_entries[0]["response_status"], 200)
        self.assertIn("admin", profile_entries[0]["response_body"] or "")

        # Verify POST /api/items was captured with payload
        item_entries = [e for e in entries if "/api/items" in e["url"]]
        self.assertEqual(len(item_entries), 1)
        self.assertEqual(item_entries[0]["method"], "POST")
        self.assertEqual(item_entries[0]["response_status"], 201)
        self.assertIn("Widget A", item_entries[0]["post_data"] or "")


if __name__ == "__main__":
    unittest.main()
