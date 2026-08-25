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
    headers_from_auth,
    load_auth_file,
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


if __name__ == "__main__":
    unittest.main()