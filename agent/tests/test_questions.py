"""
Tests for agent/questions.py (Module 17 / STORY-17.4).
"""

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent.questions import (  # noqa: E402
    ask,
    suggested_questions,
)

_TRAFFIC = [
    {"method": "POST", "url": "https://app.acme.com/api/login", "resource_type": "fetch"},
    {"method": "GET", "url": "https://api.acme.com/v1/users", "resource_type": "xhr"},
    {"method": "POST", "url": "https://api.acme.com/v1/users", "resource_type": "fetch"},
]


class TestQuestions(unittest.TestCase):
    def test_suggested_questions_detect_auth_and_write(self):
        qs = suggested_questions(_TRAFFIC)
        keys = [q["key"] for q in qs]
        self.assertIn("auth", keys)
        self.assertIn("write_handling", keys)
        self.assertIn("risk_confirmation", keys)

    def test_assume_uses_defaults(self):
        qs = suggested_questions(_TRAFFIC)
        result = ask(qs, assume=True)
        self.assertEqual(result.get("auth"), "session")
        self.assertEqual(result.get("write_handling"), "separate")
        self.assertEqual(result.get("risk_confirmation"), "auto")
        self.assertEqual(result.assumed, [q["key"] for q in qs])

    def test_interactive_chooses_option(self):
        qs = suggested_questions(_TRAFFIC)
        # Simulate user typing "1" for the first (auth) question, then default
        # (blank) for the rest.
        calls = {"n": 0}

        def fake_input(_prompt):
            calls["n"] += 1
            return "1" if calls["n"] == 1 else ""

        result = ask(qs, assume=False, input_fn=fake_input)
        self.assertEqual(result.get("auth"), "session")

    def test_interactive_blank_uses_default(self):
        qs = suggested_questions(_TRAFFIC)
        result = ask(qs, assume=False, input_fn=lambda _prompt: "")
        self.assertEqual(result.get("risk_confirmation"), "auto")


if __name__ == "__main__":
    unittest.main()