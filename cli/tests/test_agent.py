"""
Tests for the Web2Actions agent `analyze` command (Module 17 / STORY-17.1).

Verifies the CLI wiring and that cmd_analyze drives the provider-agnostic LLM
backend (mocked) to summarize captured traffic. No live API call is made.
"""

import argparse
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _make_dump(path):
    data = [
        {"method": "GET", "url": "https://api.example.com/v1/customers", "resource_type": "xhr"},
        {"method": "POST", "url": "https://abc.supabase.co/rest/v1/tasks", "resource_type": "fetch"},
        {"method": "GET", "url": "https://site.com/_next/static/chunks/x.js", "resource_type": "script"},
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


class _FakeChoice:
    def __init__(self, c):
        self.message = type("M", (), {"content": c})()


class _FakeResp:
    def __init__(self, c):
        self.choices = [_FakeChoice(c)]


class TestAnalyze(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dump = os.path.join(self.tmp, "traffic.json")
        _make_dump(self.dump)

    def test_analyze_missing_dump_returns_one(self):
        from cli import agent as agent_cli
        args = argparse.Namespace(dump="", model=None, url=None, output=None)
        self.assertEqual(agent_cli.cmd_analyze(args), 1)

    def test_analyze_drives_llm_and_reports(self):
        from cli import agent as agent_cli

        # Resolve agent.llm through the already-imported cli.agent module's helper
        # to avoid relying on the fragile bare `import agent` in the discover env.
        sys.path.insert(0, ROOT)
        from agent import llm as llm

        args = argparse.Namespace(dump=self.dump, model="openai/gpt-4o-mini", url=None, output=None)
        reply = "1. GET /v1/customers - read\n2. POST /rest/v1/tasks - write"
        with mock.patch.object(llm, "litellm") as ml:
            ml.completion.return_value = _FakeResp(reply)
            rc = agent_cli.cmd_analyze(args)
        self.assertEqual(rc, 0)
        # The LLM must have been called once.
        ml.completion.assert_called_once()

    def test_analyze_output_writes_connector(self):
        """analyze --output writes a schema-valid connector from the report."""
        from cli import agent as agent_cli
        from agent import llm as llm

        out = os.path.join(self.tmp, "connector.json")
        args = argparse.Namespace(
            dump=self.dump, model="openai/gpt-4o-mini",
            url="https://www.acme.com", output=out,
        )
        report = "1. GET https://api.acme.com/v1/users - read - list\n2. POST https://api.acme.com/v1/users - write"
        with mock.patch.object(llm, "litellm") as ml:
            ml.completion.return_value = _FakeResp(report)
            rc = agent_cli.cmd_analyze(args)
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(out))
        with open(out, encoding="utf-8") as f:
            conn = json.load(f)
        self.assertEqual(conn["name"], "www-acme-com")
        self.assertEqual(len(conn["tools"]), 2)

    def test_analyze_refuses_on_mfa_dump(self):
        """analyze calls neither the LLM nor writes output when the dump has MFA signals."""
        from cli import agent as agent_cli
        from agent import llm as llm

        dump = os.path.join(self.tmp, "mfa_traffic.json")
        with open(dump, "w", encoding="utf-8") as f:
            json.dump([{"method": "GET", "url": "https://app.acme.com/verify/otp",
                        "resource_type": "fetch"}], f)

        out = os.path.join(self.tmp, "should_not_exist.json")
        args = argparse.Namespace(dump=dump, model="openai/gpt-4o-mini",
                                  url="https://www.acme.com", output=out)
        with mock.patch.object(llm, "litellm") as ml:
            rc = agent_cli.cmd_analyze(args)
        self.assertEqual(rc, 1)
        ml.completion.assert_not_called()
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()