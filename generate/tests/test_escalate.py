"""
Unit tests for the sandboxed escalation runner (STORY-6.1).

Verifies that a connector which failed cheap-path validation can be repaired
into a passing connector definition via a (mocked) stronger-model LLM call,
and that if repair never succeeds the result is flagged needs_escalation.
"""

import json
import os
import sys
import unittest
from unittest import mock

# Generate package dir
GEN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if GEN_DIR not in sys.path:
    sys.path.insert(0, GEN_DIR)

from escalate import build_escalation_prompt, escalate_and_repair, load_escalation_prompt  # noqa: E402
from status import ExtractionStatus  # noqa: E402


def sample_traffic_dump() -> list:
    """Return a small filtered traffic fixture for one site."""
    return [
        {"method": "GET", "url": "https://api.example.com/customers", "resource_type": "xhr",
         "response_status": 200, "response_headers": {"content-type": "application/json"}, "response_body": '[]'},
    ]


def failing_connector() -> dict:
    """A connector dict that failed cheap-path validation (missing required auth/tools)."""
    return {"name": "example-api", "version": "1.0.0", "description": "partial"}


def valid_connector_json() -> str:
    """A connector-definition JSON string that passes the schema."""
    connector = {
        "name": "example-api",
        "version": "1.0.0",
        "description": "A repaired connector",
        "websiteUrl": "https://www.example.com",
        "auth": {"type": "apiKey", "apiKeyIn": "header", "apiKeyName": "X-API-Key"},
        "tools": [
            {
                "name": "listCustomers",
                "description": "Fetch the customer list",
                "risk": "read",
                "inputSchema": {"type": "object", "properties": {}},
                "outputSchema": {"type": "object", "properties": {}},
                "call": {"method": "GET", "url": "https://api.example.com/customers"},
            }
        ],
    }
    return json.dumps(connector)


class _FakeResponse:
    """Minimal stand-in for anyllm's Response."""

    def __init__(self, text: str):
        self._text = text

    def __str__(self):
        return self._text


class TestEscalation(unittest.TestCase):
    """Test suite for the sandboxed escalation / repair runner."""

    def test_load_escalation_prompt_from_folder(self):
        """The escalation prompt must load from the prompts folder."""
        prompt = load_escalation_prompt()
        self.assertIn("previous connector definition", prompt)
        self.assertIn("{validation_errors}", prompt)

    def test_build_escalation_prompt_includes_failure_context(self):
        """The prompt must include traffic, prior connector, and validation errors."""
        prompt = build_escalation_prompt(
            sample_traffic_dump(), failing_connector(), ["'tools' is a required property"]
        )
        self.assertIn("api.example.com/customers", prompt)
        self.assertIn("required property", prompt)
        self.assertNotIn("{traffic_dump}", prompt)

    @mock.patch("anyllm.chat")
    def test_repair_produces_passing_connector(self, mock_chat):
        """A stronger-model repair that returns valid JSON must yield a passing connector."""
        mock_chat.return_value = _FakeResponse(valid_connector_json())

        result = escalate_and_repair(
            sample_traffic_dump(),
            failing_connector(),
            ["'tools' is a required property"],
            llm_call=lambda prompt: mock_chat(prompt),
        )
        self.assertEqual(result["status"], ExtractionStatus.SUCCESS.value)
        self.assertEqual(result["connector"]["name"], "example-api")

    @mock.patch("anyllm.chat")
    def test_repair_that_never_passes_is_needs_escalation(self, mock_chat):
        """If repair never yields valid JSON, the result is flagged needs_escalation."""
        mock_chat.return_value = _FakeResponse('{"name": "still-broken"}')

        result = escalate_and_repair(
            sample_traffic_dump(),
            failing_connector(),
            ["'tools' is a required property"],
            llm_call=lambda prompt: mock_chat(prompt),
            max_attempts=2,
        )
        self.assertEqual(result["status"], ExtractionStatus.NEEDS_ESCALATION.value)
        self.assertTrue(result["errors"])


if __name__ == "__main__":
    unittest.main()