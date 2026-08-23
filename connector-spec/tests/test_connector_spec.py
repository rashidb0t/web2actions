"""
Unit tests for connector-spec validation.
Tests validation of valid, invalid, and example connector definitions.
"""

import glob
import os
import sys
import unittest

SPEC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SPEC_DIR not in sys.path:
    sys.path.insert(0, SPEC_DIR)

from validate import validate_connector, validate_connector_file, get_schema_path, load_json_file


def create_sample_connector() -> dict:
    """Helper that returns a valid sample connector dictionary."""
    return {
        "name": "sample-service",
        "version": "1.0.0",
        "description": "A sample connector for testing purposes",
        "websiteUrl": "https://example.com",
        "auth": {
            "type": "apiKey",
            "apiKeyIn": "header",
            "apiKeyName": "X-API-Key"
        },
        "tools": [
            {
                "name": "searchItems",
                "description": "Search items in the catalog",
                "risk": "read",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search keyword"
                        }
                    },
                    "required": ["query"]
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "results": {
                            "type": "array"
                        }
                    }
                },
                "call": {
                    "method": "GET",
                    "url": "https://example.com/api/items"
                }
            }
        ]
    }


class TestConnectorSpecValidator(unittest.TestCase):
    """Test suite for connector specification validation."""

    def test_valid_connector_passes(self):
        """A properly structured connector dictionary should pass validation."""
        connector = create_sample_connector()
        is_valid, error = validate_connector(connector)
        self.assertTrue(is_valid, f"Expected valid connector, got error: {error}")
        self.assertIsNone(error)

    def test_missing_required_field_fails(self):
        """Omitting a required field like 'name' must fail validation."""
        connector = create_sample_connector()
        del connector["name"]
        is_valid, error = validate_connector(connector)
        self.assertFalse(is_valid)
        self.assertIn("'name' is a required property", error)

    def test_invalid_risk_tag_fails(self):
        """A risk tag that is not read, write, or destructive must fail validation."""
        connector = create_sample_connector()
        connector["tools"][0]["risk"] = "dangerous"
        is_valid, error = validate_connector(connector)
        self.assertFalse(is_valid)
        self.assertIn("is not one of ['read', 'write', 'destructive']", error)

    def test_invalid_auth_type_fails(self):
        """An unsupported auth type must fail validation."""
        connector = create_sample_connector()
        connector["auth"]["type"] = "jwt_bearer"
        is_valid, error = validate_connector(connector)
        self.assertFalse(is_valid)
        self.assertIn("is not one of ['none', 'apiKey', 'oauth', 'basic']", error)

    def test_invalid_http_method_fails(self):
        """An unsupported HTTP method must fail validation."""
        connector = create_sample_connector()
        connector["tools"][0]["call"]["method"] = "HEAD"
        is_valid, error = validate_connector(connector)
        self.assertFalse(is_valid)
        self.assertIn("is not one of ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']", error)

    def test_nonexistent_file_fails(self):
        """Validating a non-existent file returns error."""
        is_valid, error = validate_connector_file("/non/existent/path.json")
        self.assertFalse(is_valid)
        self.assertIn("File not found", error)

    def test_schema_file_exists(self):
        """Schema file must exist and be loadable JSON."""
        schema_path = get_schema_path()
        self.assertTrue(os.path.isfile(schema_path))
        schema = load_json_file(schema_path)
        self.assertEqual(schema.get("title"), "ConnectorDefinition")

    def test_all_example_files_are_valid(self):
        """Every JSON file in packages/connector-spec/examples must pass validation."""
        examples_dir = os.path.join(SPEC_DIR, "examples")
        if not os.path.isdir(examples_dir):
            self.skipTest("No examples directory found")

        example_files = glob.glob(os.path.join(examples_dir, "*.json"))
        self.assertGreater(len(example_files), 0, "Expected at least one example file to validate")

        for file_path in example_files:
            is_valid, error = validate_connector_file(file_path)
            self.assertTrue(is_valid, f"Example '{os.path.basename(file_path)}' failed validation: {error}")


if __name__ == "__main__":
    unittest.main()
