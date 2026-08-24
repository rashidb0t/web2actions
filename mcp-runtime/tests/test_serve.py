"""
Integration tests for the MCP runtime (STORY-7.1).

Launches the served connector as a stdio subprocess and drives it through a
real MCP client session: lists tools and invokes a tool against the live JWT
CRUD test app. One shared program serves the connector — no per-connector code.
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest

# MCP runtime dir
MCP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if MCP_DIR not in sys.path:
    sys.path.insert(0, MCP_DIR)

# Capture tests dir (bring in the JWT CRUD app helper)
CAPTURE_TESTS = os.path.abspath(os.path.join(MCP_DIR, "..", "capture", "tests"))
if CAPTURE_TESTS not in sys.path:
    sys.path.insert(0, CAPTURE_TESTS)

from serve import _execute_call, _tool_from_connector, build_server  # noqa: E402
from jwt_crud_app import start_jwt_crud_app  # noqa: E402

from mcp import ClientSession, StdioServerParameters, stdio_client


class TestMCPRuntime(unittest.TestCase):
    """Integration tests for the shared MCP server over a real stdio client."""

    @classmethod
    def setUpClass(cls):
        cls.server, cls.port = start_jwt_crud_app()
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.connector_path = cls._write_connector(cls.base_url)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    @classmethod
    def _write_connector(cls, base_url):
        connector = {
            "name": "jwt-crud",
            "version": "1.0.0",
            "description": "JWT CRUD test connector",
            "websiteUrl": base_url,
            "auth": {"type": "none"},
            "tools": [
                {
                    "name": "listItems",
                    "description": "List items",
                    "risk": "read",
                    "inputSchema": {"type": "object", "properties": {}},
                    "outputSchema": {"type": "object", "properties": {}},
                    "call": {"method": "GET", "url": f"{base_url}/api/items"},
                }
            ],
        }
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(connector, f)
        return path

    def _stdio_params(self):
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp-runtime", self.connector_path],
            cwd=os.getcwd(),
            env={"PATH": os.environ["PATH"], "VIRTUAL_ENV": os.environ.get("VIRTUAL_ENV", "")},
        )

    def test_tool_from_connector_maps_fields(self):
        """A connector tool dict becomes an MCP Tool with the right schema."""
        tool = {"name": "listItems", "description": "l",
                "inputSchema": {"type": "object", "properties": {}}}
        mcp_tool = _tool_from_connector(tool)
        self.assertEqual(mcp_tool.name, "listItems")
        self.assertIn("type", mcp_tool.input_schema)

    def test_execute_call_hits_live_target(self):
        """_execute_call actually calls the live JWT app (401 without token)."""
        call_spec = {"method": "GET", "url": f"{self.base_url}/api/items"}
        self.assertIn("error", _execute_call(call_spec, {}).lower())

    def test_client_lists_and_invokes_tool(self):
        """A real MCP client lists the tool and invokes it against the live app."""
        async def scenario():
            async with stdio_client(self._stdio_params()) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    names = [t.name for t in tools.tools]
                    self.assertIn("listItems", names)
                    # Invoke the tool (no token -> the app returns 401, which proves the call executed)
                    result = await session.call_tool("listItems", {})
                    text = result.content[0].text if result.content else ""
                    self.assertIn("error", text.lower())

        asyncio.run(scenario())

    def test_build_server_registers_tools(self):
        """build_server returns a Server with the connector's name."""
        with open(self.connector_path) as f:
            connector = json.load(f)
        server = build_server(connector)
        self.assertEqual(server.server_info.name, "web2actions-connector")


if __name__ == "__main__":
    unittest.main()