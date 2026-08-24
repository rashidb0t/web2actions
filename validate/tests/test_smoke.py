"""
Integration tests for validate/smoke.py (STORY-5.1).

Runs the smoke test against the live JWT CRUD app: every tool is replayed
once, a deliberately broken tool is flagged without blocking the others.
"""

import json
import os
import sys
import threading
import unittest

# Validate package dir
VAL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if VAL_DIR not in sys.path:
    sys.path.insert(0, VAL_DIR)

# Capture package tests dir (bring in the JWT CRUD app helper)
CAPTURE_TESTS = os.path.abspath(os.path.join(VAL_DIR, "..", "capture", "tests"))
if CAPTURE_TESTS not in sys.path:
    sys.path.insert(0, CAPTURE_TESTS)

from smoke import call_tool, smoke_test_connector  # noqa: E402
from jwt_crud_app import start_jwt_crud_app  # noqa: E402


def login_for_token(base_url: str) -> str:
    """Log into the JWT app, return the bearer token embedded in the dashboard."""
    from requests import post
    resp = post(f"{base_url}/api/login", data={"username": "admin", "password": "secret123"})
    # The dashboard HTML embeds the token in data-token="...".
    html = resp.text
    start = html.find('data-token="') + len('data-token="')
    end = html.find('"', start)
    return html[start:end]


class TestSmokeTest(unittest.TestCase):
    """Validate module smoke-test integration against the live JWT app."""

    @classmethod
    def setUpClass(cls):
        cls.server, cls.port = start_jwt_crud_app()
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.token = login_for_token(cls.base_url)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_smoke_runs_all_tools_and_returns_results(self):
        """A connector's tools are all replayed and each gets a result entry."""
        connector = {
            "tools": [
                {"name": "listItems", "call": {"method": "GET", "url": f"{self.base_url}/api/items"}},
                {"name": "deleteItem", "call": {"method": "DELETE", "url": f"{self.base_url}/api/items/nope"}},
            ]
        }
        results = smoke_test_connector(connector, self.base_url, token=self.token)
        self.assertEqual(len(results), 2)
        names = {r["tool"] for r in results}
        self.assertEqual(names, {"listItems", "deleteItem"})

    def test_broken_tool_flagged_without_blocking_others(self):
        """A tool hitting a non-existent endpoint is flagged, but the good tool still passes."""
        connector = {
            "tools": [
                {"name": "good", "call": {"method": "GET", "url": f"{self.base_url}/api/items"}},
                {"name": "broken", "call": {"method": "GET", "url": f"{self.base_url}/api/missing"}},
            ]
        }
        results = smoke_test_connector(connector, self.base_url, token=self.token)
        by_name = {r["tool"]: r for r in results}
        self.assertTrue(by_name["good"]["ok"])
        self.assertFalse(by_name["broken"]["ok"])
        self.assertEqual(by_name["broken"]["status"], 404)

    def test_unauthorized_call_is_flagged_failed(self):
        """A tool without a token that hits a protected endpoint must be flagged."""
        result = call_tool(
            {"name": "listItems", "call": {"method": "GET", "url": f"{self.base_url}/api/items"}},
            self.base_url,
            token=None,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], 401)


if __name__ == "__main__":
    unittest.main()