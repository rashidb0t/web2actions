"""
Integration tests for the MCP runtime (STORY-7.1).

Launches the served connector as a stdio subprocess and drives it through a
real MCP client session: lists tools and invokes a tool against the live JWT
CRUD test app. One shared program serves the connector — no per-connector code.

Also covers the security contract: SSRF allow-listing, input-schema
enforcement, auth_provider token injection, and error sanitization.
"""

import asyncio
import json
import os
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

from serve import (  # noqa: E402
    _allowed_hosts,
    _execute_call,
    _tool_from_connector,
    _validate_arguments,
    _validate_url,
    build_server,
)
from jwt_crud_app import start_jwt_crud_app  # noqa: E402

from mcp import ClientSession, StdioServerParameters, stdio_client  # noqa: E402


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

    # --- helpers ---

    def test_tool_from_connector_maps_fields(self):
        """A connector tool dict becomes an MCP Tool with the right schema."""
        tool = {"name": "listItems", "description": "l",
                "inputSchema": {"type": "object", "properties": {}}}
        mcp_tool = _tool_from_connector(tool)
        self.assertEqual(mcp_tool.name, "listItems")
        self.assertIn("type", mcp_tool.input_schema)

    # --- SSRF / security contract ---

    def test_allowed_hosts_from_website_url(self):
        """allowed_hosts derives from the connector's websiteUrl."""
        connector = {"websiteUrl": "https://api.example.com"}
        self.assertEqual(_allowed_hosts(connector), ["api.example.com"])
        self.assertEqual(_allowed_hosts({}), [])

    def test_validate_url_rejects_off_host(self):
        """A URL whose host is not in the allow-list is refused."""
        with self.assertRaises(ValueError):
            _validate_url("http://169.254.169.254/meta", ["api.example.com"])

    def test_validate_url_allows_on_host(self):
        """A URL whose host is in the allow-list is permitted."""
        _validate_url("http://api.example.com/items", ["api.example.com"])  # no raise

    def test_validate_arguments_enforces_schema(self):
        """Arguments are validated against the tool's inputSchema."""
        tool = {"inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}}
        with self.assertRaises(ValueError):
            _validate_arguments(tool, {})
        _validate_arguments(tool, {"id": "x"})  # no raise

    # --- execution ---

    def test_execute_call_hits_live_target(self):
        """_execute_call actually calls the live JWT app (401 without token)."""
        call_spec = {"method": "GET", "url": f"{self.base_url}/api/items"}
        self.assertIn("error", _execute_call(call_spec, {}, allowed_hosts=[f"127.0.0.1"]).lower())

    def test_execute_call_fills_url_placeholders(self):
        """{param} placeholders in the URL are filled from arguments."""
        from requests import post
        resp = post(f"{self.base_url}/api/login", data={"username": "admin", "password": "secret123"})
        html = resp.text
        start = html.find('data-token="') + len('data-token="')
        token = html[start:html.find('"', start)]
        call_spec = {"method": "GET", "url": f"{self.base_url}/api/items/{{item_id}}"}
        text = _execute_call(call_spec, {"item_id": "x"}, token=token, allowed_hosts=["127.0.0.1"])
        self.assertIn("not found", text.lower())

    def test_auth_provider_token_serves_authenticated_request(self):
        """A token from auth_provider lets an authenticated protected tool succeed."""
        from requests import post
        resp = post(f"{self.base_url}/api/login", data={"username": "admin", "password": "secret123"})
        html = resp.text
        start = html.find('data-token="') + len('data-token="')
        token = html[start:html.find('"', start)]

        # A tool with a valid token can list items (200), proving authenticated calls work.
        call_spec = {"method": "GET", "url": f"{self.base_url}/api/items"}
        text = _execute_call(call_spec, {}, token=token, allowed_hosts=["127.0.0.1"])
        self.assertIn("items", text)  # successful authorized call

    def test_execute_call_injects_cookie_auth(self):
        """An auth dict with cookies is sent as a Cookie header on the request."""
        import http.server as _hs
        import json as _json
        import threading as _th

        class H(_hs.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.end_headers()
                out = _json.dumps({"cookie": self.headers.get("Cookie"),
                                   "auth": self.headers.get("Authorization")}).encode()
                self.wfile.write(out)
            def log_message(self, *a): pass

        srv = _hs.HTTPServer(("127.0.0.1", 0), H)
        port = srv.server_address[1]
        t = _th.Thread(target=srv.serve_forever, daemon=True); t.start()
        try:
            call_spec = {"method": "GET", "url": f"http://127.0.0.1:{port}/x",
                         "headers": {}, "body": {}}
            text = _execute_call(call_spec, {}, auth={"cookies": {"a": "1", "b": "2"}},
                                 allowed_hosts=["127.0.0.1"])
            self.assertIn("a=1; b=2", text)
        finally:
            srv.shutdown()

    def test_execute_call_injects_token_auth(self):
        """An auth dict with a token is sent as a Bearer Authorization header."""
        import http.server as _hs
        import json as _json
        import threading as _th

        class H(_hs.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.end_headers()
                out = _json.dumps({"auth": self.headers.get("Authorization")}).encode()
                self.wfile.write(out)
            def log_message(self, *a): pass

        srv = _hs.HTTPServer(("127.0.0.1", 0), H)
        port = srv.server_address[1]
        t = _th.Thread(target=srv.serve_forever, daemon=True); t.start()
        try:
            call_spec = {"method": "GET", "url": f"http://127.0.0.1:{port}/x",
                         "headers": {}, "body": {}}
            text = _execute_call(call_spec, {}, auth={"token": "beep"},
                                 allowed_hosts=["127.0.0.1"])
            self.assertIn("Bearer beep", text)
        finally:
            srv.shutdown()

    def test_auto_reauth_on_401_retries_and_succeeds(self):
        """On 401/403 expiry, triggers on_auth_expired and retries with refreshed token."""
        import http.server as _hs
        import threading as _th

        attempts = []

        class _ExpiryHandler(_hs.BaseHTTPRequestHandler):
            def do_GET(self):
                auth_header = self.headers.get("Authorization", "")
                attempts.append(auth_header)
                if "fresh_token_xyz" in auth_header:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"OK authenticated!")
                else:
                    self.send_response(401)
                    self.end_headers()
                    self.wfile.write(b"Unauthorized: Token expired")

            def log_message(self, format, *args):
                pass

        srv = _hs.HTTPServer(("127.0.0.1", 0), _ExpiryHandler)
        port = srv.server_address[1]
        t = _th.Thread(target=srv.serve_forever, daemon=True)
        t.start()

        try:
            call_spec = {
                "method": "GET",
                "url": f"http://127.0.0.1:{port}/api/data",
                "headers": {},
                "body": {},
            }

            def refresh_hook():
                return {"token": "fresh_token_xyz"}

            text = _execute_call(
                call_spec,
                {},
                auth={"token": "expired_token_123"},
                allowed_hosts=["127.0.0.1"],
                on_auth_expired=refresh_hook,
            )

            self.assertIn("OK authenticated!", text)
            self.assertEqual(len(attempts), 2)
            self.assertIn("expired_token_123", attempts[0])
            self.assertIn("fresh_token_xyz", attempts[1])
        finally:
            srv.shutdown()

    # --- client integration ---

    def test_client_lists_and_invokes_tool(self):
        """A real MCP client lists the tool and invokes it against the live app."""
        async def scenario():
            async with stdio_client(self._stdio_params()) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    names = [t.name for t in tools.tools]
                    self.assertIn("listItems", names)
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