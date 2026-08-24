"""
Unit tests for mechanical risk tagging (STORY-5.2).
"""

import os
import sys
import unittest

# Validate package dir
VAL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if VAL_DIR not in sys.path:
    sys.path.insert(0, VAL_DIR)

from risk import (  # noqa: E402
    risk_from_name_and_method,
    tag_all_tool_risks,
    tag_tool_risk,
)


class TestRiskTagging(unittest.TestCase):
    """Test suite for mechanical risk classification of tools."""

    def test_get_is_read(self):
        """A GET tool is tagged read."""
        self.assertEqual(risk_from_name_and_method("listCustomers", "GET"), "read")

    def test_post_is_write(self):
        """A POST tool is tagged write."""
        self.assertEqual(risk_from_name_and_method("createCustomer", "POST"), "write")

    def test_put_is_write(self):
        """A PUT tool is tagged write."""
        self.assertEqual(risk_from_name_and_method("updateCustomer", "PUT"), "write")

    def test_delete_is_destructive(self):
        """A DELETE tool is tagged destructive."""
        self.assertEqual(risk_from_name_and_method("deleteCustomer", "DELETE"), "destructive")

    def test_destructive_keyword_overrides_method(self):
        """A tool named delete/remove/transfer/send is destructive even via GET/POST."""
        self.assertEqual(risk_from_name_and_method("removeItem", "GET"), "destructive")
        self.assertEqual(risk_from_name_and_method("sendEmail", "POST"), "destructive")
        self.assertEqual(risk_from_name_and_method("transferFunds", "PUT"), "destructive")

    def test_tag_tool_sets_risk_field(self):
        """tag_tool_risk sets the risk field from the tool's method."""
        tool = {"name": "listCustomers", "call": {"method": "GET", "url": "x"}}
        tagged = tag_tool_risk(tool)
        self.assertEqual(tagged["risk"], "read")

    def test_tag_all_tools(self):
        """tag_all_tool_risks tags every tool in a connector."""
        connector = {
            "tools": [
                {"name": "list", "call": {"method": "GET", "url": "x"}},
                {"name": "create", "call": {"method": "POST", "url": "x"}},
                {"name": "delete", "call": {"method": "DELETE", "url": "x"}},
            ]
        }
        tag_all_tool_risks(connector)
        risks = [t["risk"] for t in connector["tools"]]
        self.assertEqual(risks, ["read", "write", "destructive"])


if __name__ == "__main__":
    unittest.main()