"""
Unit tests for the Web2Actions CLI (module 15, STORY-15.1).

Tests the wrapper subcommands end-to-end: validate (valid + invalid), and the
generate BYOK error path. generate's LLM call is not exercised with a real key
(budget safety) — we test that a missing key yields a clean, exit-1 message.
"""

import json
import os
import sys
import unittest
from unittest import mock

CLI_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if CLI_DIR not in sys.path:
    sys.path.insert(0, CLI_DIR)

ROOT = os.path.dirname(CLI_DIR)
SPEC_DIR = os.path.join(ROOT, "connector-spec")
if SPEC_DIR not in sys.path:
    sys.path.insert(0, SPEC_DIR)

from cli.main import cmd_capture as cli_capture  # noqa: E402
from cli.main import cmd_generate as cli_generate  # noqa: E402
from cli.main import cmd_validate as cli_validate  # noqa: E402
from cli.main import main as cli_main  # noqa: E402
from cli.main import _resolve_model  # noqa: E402


class TestCliValidate(unittest.TestCase):
    """validate subcommand returns 0 for a valid connector, 1 for invalid."""

    def setUp(self):
        self.valid = os.path.join(SPEC_DIR, "examples", "simple-crm.json")

    def test_validate_valid_returns_zero(self):
        args = mock.Mock(connector=self.valid)
        self.assertEqual(cli_validate(args), 0)

    def test_validate_invalid_returns_nonzero(self):
        import tempfile
        bad = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump({"name": "x"}, bad)  # missing required fields
        bad.close()
        args = mock.Mock(connector=bad.name)
        self.assertEqual(cli_validate(args), 1)
        os.unlink(bad.name)


class TestCliGenerate(unittest.TestCase):
    """generate surfaces a clean BYOK error (exit 1) when no LLM provider is set."""

    def test_generate_missing_key_returns_one(self):
        import tempfile
        traffic = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump([], traffic)
        traffic.close()
        args = mock.Mock(traffic=traffic.name, model=None, output="out.json")

        class FakeResult:
            status = "needs_escalation"
            errors = ["no provider"]

        with mock.patch("litellm.completion", side_effect=RuntimeError("No LLM provider is available")):
            code = cli_generate(args)
        self.assertEqual(code, 1)
        os.unlink(traffic.name)

    def test_resolve_model_defaults(self):
        self.assertEqual(_resolve_model(None), "gpt-4o-mini")
        self.assertEqual(_resolve_model("claude-sonnet-4"), "claude-sonnet-4")


class TestCliCapture(unittest.TestCase):
    """capture subcommand behaviors that don't need a live browser."""

    def test_capture_login_requires_credentials(self):
        """--login without --username/--password returns nonzero without opening a browser."""
        args = mock.Mock(url="https://example.com", login=True, username=None, password=None)
        self.assertEqual(cli_capture(args), 1)


if __name__ == "__main__":
    unittest.main()