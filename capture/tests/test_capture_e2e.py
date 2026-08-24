"""
End-to-end capture test (STORY-3.4).

Drives the full capture pipeline -- BrowserSession -> NetworkRecorder ->
filter_traffic -- against a JWT-protected CRUD test app and asserts that the
resulting filtered dump keeps the login call and real CRUD calls (with response
bodies present) while stripping the app's analytics and static-asset noise.
"""

import os
import sys
import threading
import unittest
from http.client import HTTPConnection

TESTS_DIR = os.path.abspath(os.path.dirname(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

CAPTURE_PKG_DIR = os.path.abspath(os.path.join(TESTS_DIR, ".."))
if CAPTURE_PKG_DIR not in sys.path:
    sys.path.insert(0, CAPTURE_PKG_DIR)

from jwt_crud_app import make_jwt, verify_jwt, start_jwt_crud_app  # noqa: E402
from session import BrowserSession, perform_login  # noqa: E402
from recorder import NetworkRecorder  # noqa: E402
from filter import filter_traffic  # noqa: E402


class TestJwtCrudAppAuth(unittest.TestCase):
    """Sanity checks for the JWT test app's token handling."""

    def test_token_roundtrip_and_tamper_detection(self):
        token = make_jwt("admin")
        self.assertEqual(verify_jwt(token), "admin")
        # A token with a modified signature must not verify.
        tampered = token[:-2] + ("ab" if token[-2:] != "ab" else "cd")
        self.assertIsNone(verify_jwt(tampered))
        self.assertIsNone(verify_jwt("not-a-jwt"))

    def test_protected_endpoint_requires_token(self):
        server, port = start_jwt_crud_app()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/api/items")
            response = conn.getresponse()
            self.assertEqual(response.status, 401)
            conn.close()
        finally:
            server.shutdown()
            server.server_close()


class TestEndToEndCapture(unittest.TestCase):
    """End-to-end capture against the JWT CRUD test app."""

    @classmethod
    def setUpClass(cls):
        cls.server, cls.port = start_jwt_crud_app()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_full_pipeline_produces_filtered_dump(self):
        recorder = NetworkRecorder()

        with BrowserSession(headless=True) as page:
            recorder.start(page)

            # 1. Log in through the form. Server issues a JWT and renders the
            #    dashboard, which carries the token for the follow-up API calls.
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

            # 2. Drive noise + real CRUD calls against the protected API.
            page.evaluate(
                """
                (base) => {
                  const token = document.querySelector('#dashboard').dataset.token;
                  const auth = { Authorization: 'Bearer ' + token };
                  async function run() {
                    // Noise the capture must strip.
                    await fetch(base + '/assets/app.css');
                    await fetch(base + '/analytics/track', { method: 'POST' });
                    // Real CRUD calls against the JWT-protected API.
                    await fetch(base + '/api/items', { headers: auth });
                    await fetch(base + '/api/items', {
                      method: 'POST',
                      headers: Object.assign({ 'Content-Type': 'application/json' }, auth),
                      body: JSON.stringify({ name: 'Widget A', price: 42 }),
                    });
                    const list = await (await fetch(base + '/api/items', { headers: auth })).json();
                    const id = list.items[0].id;
                    await fetch(base + '/api/items/' + id, { method: 'DELETE', headers: auth });
                  }
                  return run();
                }
                """,
                self.base_url,
            )

            recorder.stop()

        raw = recorder.get_entries()
        filtered = filter_traffic(raw)

        # The raw capture must have included noise for the filter to be meaningful.
        raw_urls = [e["url"] for e in raw]
        self.assertTrue(any("/assets/app.css" in u for u in raw_urls))
        self.assertTrue(any("/analytics/track" in u for u in raw_urls))

        # --- Login call is present in the filtered dump ---
        login = [e for e in filtered if e["url"].endswith("/api/login") and e["method"] == "POST"]
        self.assertEqual(len(login), 1, "login POST missing from filtered dump")
        self.assertEqual(login[0]["response_status"], 200)
        self.assertIn("Welcome admin", login[0]["response_body"] or "")

        # --- At least one real CRUD call is present ---
        crud = [e for e in filtered if "/api/items" in e["url"] and e["method"] in {"GET", "POST", "DELETE"}]
        self.assertGreaterEqual(len(crud), 1, "no real CRUD call in filtered dump")
        self.assertEqual(crud[0]["response_status"], 200)

        # --- Response bodies present on the real calls ---
        with_bodies = [e for e in filtered if e["response_body"]]
        self.assertTrue(any("/api/login" in e["url"] for e in with_bodies))
        self.assertTrue(any("/api/items" in e["url"] for e in with_bodies))

        # --- Noise stripped ---
        filtered_urls = [e["url"] for e in filtered]
        self.assertFalse(any("/assets/app.css" in u for u in filtered_urls))
        self.assertFalse(any("/analytics/track" in u for u in filtered_urls))


if __name__ == "__main__":
    unittest.main()
