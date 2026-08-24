"""
Unit tests for generate/extract.py (STORY-4.1).

Validates that a filtered traffic dump produces connector-definition JSON
that passes the module 1 connector-spec validator. The LLM call is patched
(mocked) so no live API budget is used, but the real litellm.completion path is
exercised through the patch.
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

# Connector-spec package dir (for direct validator use)
SPEC_DIR = os.path.abspath(os.path.join(GEN_DIR, "..", "connector-spec"))
if SPEC_DIR not in sys.path:
    sys.path.insert(0, SPEC_DIR)

from extract import (  # noqa: E402
    build_extraction_prompt,
    extract_connector_definition,
    load_extraction_prompt,
)
from validate import validate_connector  # noqa: E402


def sample_traffic_dump() -> list:
    """Return a small filtered traffic fixture for one site."""
    return [
        {"method": "POST", "url": "https://api.example.com/auth/login", "resource_type": "fetch",
         "response_status": 200, "response_headers": {"content-type": "application/json"}, "response_body": '{"token":"abc"}'},
        {"method": "GET", "url": "https://api.example.com/customers", "resource_type": "xhr",
         "response_status": 200, "response_headers": {"content-type": "application/json"}, "response_body": '[]'},
        {"method": "POST", "url": "https://api.example.com/customers", "resource_type": "fetch",
         "response_status": 201, "response_headers": {"content-type": "application/json"}, "post_data": '{"name":"Acme"}'},
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


class TestExtraction(unittest.TestCase):
    """Test suite for traffic-to-connector extraction."""

    def test_load_extraction_prompt_from_folder(self):
        """The prompt must load from the prompts folder, not be hardcoded."""
        prompt = load_extraction_prompt()
        self.assertIn("Traffic dump:", prompt)
        self.assertIn("{traffic_dump}", prompt)

    def test_build_extraction_prompt_includes_dump(self):
        """The prompt must embed the traffic dump so the model sees it."""
        prompt = build_extraction_prompt(sample_traffic_dump())
        self.assertIn("api.example.com/auth/login", prompt)
        self.assertNotIn("{traffic_dump}", prompt)

    @mock.patch("litellm.completion")
    def test_extract_returns_valid_connector(self, mock_chat):
        """A mocked LLM returning valid JSON must produce a connector that passes validation."""
        mock_chat.return_value = _FakeResponse(valid_connector_json())

        connector = extract_connector_definition(sample_traffic_dump(), model="test-model")

        mock_chat.assert_called_once()
        is_valid, error = validate_connector(connector)
        self.assertTrue(is_valid, f"Extracted connector invalid: {error}")
        self.assertEqual(connector["name"], "example-api")

    @mock.patch("litellm.completion")
    def test_extract_raises_on_invalid_connector(self, mock_chat):
        """An LLM response that is valid JSON but violates the schema must raise."""
        bad_connector = json.dumps({"name": "example-api", "version": "1.0.0"})  # missing required tools/auth
        mock_chat.return_value = _FakeResponse(bad_connector)

        with self.assertRaises(ValueError):
            extract_connector_definition(sample_traffic_dump(), model="test-model")

    @mock.patch("litellm.completion")
    def test_extract_raises_on_non_object_json(self, mock_chat):
        """A JSON response that is not an object (e.g. a list) must raise."""
        mock_chat.return_value = _FakeResponse("[]")

        with self.assertRaises(ValueError):
            extract_connector_definition(sample_traffic_dump(), model="test-model")


if __name__ == "__main__":
    unittest.main()