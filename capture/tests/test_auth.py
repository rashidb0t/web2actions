"""
Tests for capture/auth.py and the serve --auth wiring (Module 18 / Option A).
"""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CAPTURE = os.path.join(ROOT, "capture")
for p in (ROOT, CAPTURE):
    if p not in sys.path:
        sys.path.insert(0, p)

from auth import (  # noqa: E402
    auth_provider_from_file,
    extract_cookies_from_context,
    extract_session,
    extract_token_from_entries,
    headers_from_auth,
    load_auth_file,
    save_auth_file,
)


class TestAuthFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _write(self, data):
        path = os.path.join(self.tmp, "auth.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return path

    def test_load_token(self):
        path = self._write({"token": "abc123"})
        self.assertEqual(load_auth_file(path)["token"], "abc123")

    def test_load_cookies(self):
        path = self._write({"cookies": {"sessionid": "x", "csrf": "y"}})
        self.assertEqual(load_auth_file(path)["cookies"]["sessionid"], "x")

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_auth_file(os.path.join(self.tmp, "nope.json"))

    def test_invalid_shape_raises(self):
        path = self._write({"foo": "bar"})
        with self.assertRaises(ValueError):
            load_auth_file(path)

    def test_headers_from_token(self):
        h = headers_from_auth({"token": "tok1"})
        self.assertEqual(h["Authorization"], "Bearer tok1")

    def test_headers_from_cookies(self):
        h = headers_from_auth({"cookies": {"a": "1", "b": "2"}})
        self.assertEqual(h["Cookie"], "a=1; b=2")

    def test_provider_returns_loaded(self):
        path = self._write({"token": "t1"})
        provider = auth_provider_from_file(path)
        self.assertEqual(provider()["token"], "t1")

    def test_save_auth_file_creates_file_with_chmod_600(self):
        path = os.path.join(self.tmp, "sub", "saved_auth.json")
        saved = save_auth_file(path, {"token": "jwt-secret-xyz", "cookies": {"session": "s1"}})
        self.assertTrue(os.path.exists(saved))
        loaded = load_auth_file(saved)
        self.assertEqual(loaded["token"], "jwt-secret-xyz")
        self.assertEqual(loaded["cookies"]["session"], "s1")
        # Check permissions: owner read/write (0o600 or 0o100600)
        mode = oct(os.stat(saved).st_mode & 0o777)
        self.assertEqual(mode, "0o600")

    def test_save_auth_file_rejects_empty_data(self):
        path = os.path.join(self.tmp, "empty.json")
        with self.assertRaises(ValueError):
            save_auth_file(path, {})

    def test_extract_token_from_entries(self):
        entries = [
            {"request": {"url": "https://api.example.com/items", "headers": {"Content-Type": "application/json"}}},
            {"request": {"url": "https://api.example.com/data", "headers": {"Authorization": "Bearer my-jwt-token"}}},
        ]
        token = extract_token_from_entries(entries)
        self.assertEqual(token, "my-jwt-token")

    def test_extract_cookies_from_mock_context(self):
        class MockContext:
            def cookies(self):
                return [{"name": "auth_cookie", "value": "secret123", "domain": "example.com"}]

        cookies = extract_cookies_from_context(MockContext())
        self.assertEqual(cookies, {"auth_cookie": "secret123"})

    def test_extract_session_combines_token_and_cookies(self):
        class MockContext:
            def cookies(self):
                return [{"name": "sid", "value": "val1"}]

        entries = [
            {"request": {"headers": {"authorization": "Bearer token-abc"}}},
        ]
        auth = extract_session(context=MockContext(), entries=entries)
        self.assertEqual(auth["token"], "token-abc")
        self.assertEqual(auth["cookies"]["sid"], "val1")


if __name__ == "__main__":
    unittest.main()