"""
Unit tests for generate/extract.py (STORY-4.1).

Validates that a filtered traffic dump produces connector-definition JSON
that passes the module 1 connector-spec validator, via a mocked LLM call
(no live API budget used).
"""

import json
import os
import sys
import unittest

# Generate package dir
GEN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if GEN_DIR not in sys.path:
    sys.path.insert(0, GEN_DIR)

# Connector-spec package dir (for direct validator use)
SPEC_DIR = os.path.abspath(os.path.join(GEN_DIR, "..", "connector-spec"))
if SPEC_DIR not in sys.path:
    sys.path.insert(0, SPEC_DIR)

from extract import build_extraction_prompt, extract_connector_definition  # noqa: E402
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


class TestExtraction(unittest.TestCase):
    """Test suite for traffic-to-connector extraction."""

    def test_build_extraction_prompt_includes_dump(self):
        """The prompt must embed the traffic dump so the model sees it."""
        dump = sample_traffic_dump()
        prompt = build_extraction_prompt(dump)
        self.assertIn("api.example.com/auth/login", prompt)
        self.assertIn("Traffic dump:", prompt)

    def test_extract_returns_valid_connector(self):
        """A mocked LLM call returning valid JSON must produce a connector that passes validation."""
        mock_llm = lambda prompt: valid_connector_json()  # noqa: E731

        connector = extract_connector_definition(sample_traffic_dump(), mock_llm)
        is_valid, error = validate_connector(connector)
        self.assertTrue(is_valid, f"Extracted connector invalid: {error}")
        self.assertEqual(connector["name"], "example-api")

    def test_extract_raises_on_invalid_connector(self):
        """An LLM response that is valid JSON but violates the schema must raise."""
        bad_connector = json.dumps({"name": "example-api", "version": "1.0.0"})  # missing required tools/auth
        mock_llm = lambda prompt: bad_connector  # noqa: E731

        with self.assertRaises(ValueError):
            extract_connector_definition(sample_traffic_dump(), mock_llm)

    def test_extract_raises_on_non_object_json(self):
        """A JSON response that is not an object (e.g. a list) must raise."""
        mock_llm = lambda prompt: "[]"  # noqa: E731

        with self.assertRaises(ValueError):
            extract_connector_definition(sample_traffic_dump(), mock_llm)


if __name__ == "__main__":
    unittest.main()