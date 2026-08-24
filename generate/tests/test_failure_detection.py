"""
Unit tests for generate failure detection (STORY-4.2).

Verifies that when the cheap-path extraction produces invalid output, the
job result is flagged as needs_escalation — never silently marked done.
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

from extract import run_extraction_job, load_extraction_prompt  # noqa: E402
from status import ExtractionStatus  # noqa: E402


def sample_traffic_dump() -> list:
    """Return a small filtered traffic fixture for one site."""
    return [
        {"method": "POST", "url": "https://api.example.com/auth/login", "resource_type": "fetch",
         "response_status": 200, "response_headers": {"content-type": "application/json"}, "response_body": '{"token":"abc"}'},
        {"method": "GET", "url": "https://api.example.com/customers", "resource_type": "xhr",
         "response_status": 200, "response_headers": {"content-type": "application/json"}, "response_body": '[]'},
    ]


def valid_connector_json() -> str:
    """Return a connector-definition JSON string that passes the schema."""
    connector = {
        "name": "example-api",
        "version": "1.0.0",
        "description": "A generated connector for example.com",
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
    """Minimal stand-in for litellm.completion's response object."""

    def __init__(self, text: str):
        self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]


class TestFailureDetection(unittest.TestCase):
    """Test suite for extraction failure detection and escalation flagging."""

    @mock.patch("litellm.completion")
    def test_invalid_json_is_needs_escalation(self, mock_chat):
        """An LLM returning invalid JSON must be flagged needs_escalation, never done."""
        mock_chat.return_value = _FakeResponse("This is not json at all")

        result = run_extraction_job(sample_traffic_dump(), model="test-model")
        self.assertEqual(result["status"], ExtractionStatus.NEEDS_ESCALATION.value)
        self.assertIsNone(result["connector"])
        self.assertTrue(result["errors"])

    @mock.patch("litellm.completion")
    def test_schema_invalid_is_needs_escalation(self, mock_chat):
        """Connector JSON that violates the schema must be flagged needs_escalation."""
        bad_connector = json.dumps({"name": "example-api", "version": "1.0.0"})  # missing tools/auth
        mock_chat.return_value = _FakeResponse(bad_connector)

        result = run_extraction_job(sample_traffic_dump(), model="test-model")
        self.assertEqual(result["status"], ExtractionStatus.NEEDS_ESCALATION.value)
        self.assertIsNotNone(result["connector"])
        self.assertTrue(result["errors"])

    @mock.patch("litellm.completion")
    def test_valid_connector_is_success(self, mock_chat):
        """A valid extraction must be marked success with the connector attached."""
        mock_chat.return_value = _FakeResponse(valid_connector_json())

        result = run_extraction_job(sample_traffic_dump(), model="test-model")
        self.assertEqual(result["status"], ExtractionStatus.SUCCESS.value)
        self.assertEqual(result["connector"]["name"], "example-api")
        self.assertNotIn("errors", result)

    def test_status_enum_values(self):
        """The status enum exposes the two required outcome states."""
        self.assertEqual(ExtractionStatus.SUCCESS.value, "success")
        self.assertEqual(ExtractionStatus.NEEDS_ESCALATION.value, "needs_escalation")


if __name__ == "__main__":
    unittest.main()