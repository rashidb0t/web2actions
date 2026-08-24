"""
Tests for agent/to_connector.py (Module 17 / STORY-17.3).

Verifies that discovered API endpoints become a schema-valid connector
definition with mechanical risk tags, and that the analyze report parser
handles common report formats. No LLM call is made.
"""

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent.to_connector import (  # noqa: E402
    build_connector,
    parse_report,
)

_REPORT = """
1. GET https://api.acme.com/v1/users - read - list users
2. POST https://api.acme.com/v1/users - write - create user
3. DELETE https://api.acme.com/v1/users/33 - destructive - delete user
4. POST https://graph.acme.com/graphql - write - run mutation
"""


class TestToConnector(unittest.TestCase):
    def test_parse_report_extracts_urls_and_methods(self):
        eps = parse_report(_REPORT)
        self.assertEqual(len(eps), 4)
        methods = [e["method"] for e in eps]
        self.assertEqual(methods, ["GET", "POST", "DELETE", "POST"])

    def test_build_connector_is_schema_valid(self):
        eps = parse_report(_REPORT)
        conn = build_connector(eps, name="acme", website_url="https://www.acme.com")
        # Connector is structurally valid (build_connector validated it).
        self.assertEqual(conn["name"], "acme")
        self.assertEqual(len(conn["tools"]), 4)

    def test_risk_maps_from_method(self):
        eps = parse_report(_REPORT)
        conn = build_connector(eps, name="acme", website_url="https://www.acme.com")
        risks = [t["risk"] for t in conn["tools"]]
        self.assertEqual(risks, ["read", "write", "destructive", "write"])

    def test_empty_endpoints_builds_valid_empty_connector(self):
        conn = build_connector([], name="empty", website_url="https://e.com")
        self.assertEqual(conn["tools"], [])


if __name__ == "__main__":
    unittest.main()