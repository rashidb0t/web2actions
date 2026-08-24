"""
Tests for agent/guards.py challenge detection (Module 17 / STORY-17.5).
"""

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent.guards import (  # noqa: E402
    CHALLENGE_MESSAGE,
    detect_challenges,
)


class TestGuards(unittest.TestCase):
    def test_clean_traffic_not_blocked(self):
        entries = [
            {"url": "https://api.acme.com/v1/users", "method": "GET", "response_body": ""},
            {"url": "https://api.acme.com/v1/login", "method": "POST", "response_body": '{"ok": true}'},
        ]
        verdict = detect_challenges(entries)
        self.assertFalse(verdict["blocked"])
        self.assertEqual(verdict["reasons"], [])

    def test_mfa_url_blocks(self):
        entries = [{"url": "https://app.acme.com/verify/otp", "method": "GET", "response_body": ""}]
        verdict = detect_challenges(entries)
        self.assertTrue(verdict["blocked"])
        self.assertIn("MFA", verdict["reasons"][0])

    def test_captcha_url_blocks(self):
        entries = [{"url": "https://app.acme.com/?g-recaptcha", "method": "GET", "response_body": ""}]
        verdict = detect_challenges(entries)
        self.assertTrue(verdict["blocked"])
        self.assertIn("CAPTCHA", verdict["reasons"][0])

    def test_bot_body_blocks(self):
        entries = [{"url": "https://site.com/", "method": "GET", "resource_type": "document",
                    "response_body": "Just a moment... verifying you are human"}]
        verdict = detect_challenges(entries)
        self.assertTrue(verdict["blocked"])
        self.assertIn("anti-bot", verdict["reasons"][0])

    def test_page_text_mfa_blocks(self):
        entries = [{"url": "https://app.acme.com/", "method": "GET", "response_body": ""}]
        verdict = detect_challenges(entries, page_text="Enter your two-factor authentication code to continue")
        self.assertTrue(verdict["blocked"])

    def test_no_false_positive_on_benign(self):
        entries = [
            {"url": "https://api.acme.com/v2/items?page=1", "method": "GET", "response_body": "[]"},
        ]
        verdict = detect_challenges(entries)
        self.assertFalse(verdict["blocked"])
        # 'verification' substrings in a benign body must not trigger incorrectly
        verdict2 = detect_challenges([{"url": "https://api.acme.com/v1/status",
                                       "method": "GET", "response_body": "verified ok"}])
        self.assertFalse(verdict2["blocked"])

    def test_message_is_clear(self):
        self.assertIn("does not support", CHALLENGE_MESSAGE)


if __name__ == "__main__":
    unittest.main()