"""
JWT CRUD test app for Web2Actions end-to-end capture testing.

A self-contained, stdlib-only HTTP server that mimics a real target site:
- An HTML login form (POST /api/login) that issues a JWT on success.
- JWT-protected CRUD endpoints (/api/items) that require a Bearer token.
- Deliberate noise (a static stylesheet and an analytics endpoint) so the
  capture noise filter can be exercised end to end.

No production code depends on this; it exists only so an automated test can
drive the full capture pipeline against a realistic login + CRUD flow.
"""

import base64
import hashlib
import hmac
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs

JWT_SECRET = "web2actions-e2e-test-secret"

VALID_CREDENTIALS = {"admin": "secret123"}

HEADER = {"alg": "HS256", "typ": "JWT"}


def _b64(data: bytes) -> str:
    """URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64_decode(segment: str) -> bytes:
    """Decode a URL-safe base64 segment, re-adding padding if needed."""
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def make_jwt(sub: str, secret: str = JWT_SECRET) -> str:
    """Create a minimal HS256 JWT for the given subject."""
    body = {"sub": sub}
    signing_input = _b64(json.dumps(HEADER, separators=(",", ":")).encode("utf-8")) + "." + \
        _b64(json.dumps(body, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return signing_input + "." + _b64(signature)


def verify_jwt(token: str, secret: str = JWT_SECRET) -> Optional[str]:
    """Return the subject if the JWT is well-formed and signed, else None."""
    try:
        signing_input, signature = token.rsplit(".", 1)
        expected = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64_decode(signature), expected):
            return None
        payload = json.loads(_b64_decode(signing_input.split(".", 1)[1]))
        return payload.get("sub")
    except Exception:
        return None


class JWTCrudApp(BaseHTTPRequestHandler):
    """HTTP handler implementing the JWT CRUD test app."""

    @property
    def base_url(self) -> str:
        return f"http://{self.server.server_address[0]}:{self.server.server_address[1]}"

    # --- helpers ---

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, data: Dict[str, Any]) -> None:
        self._send(status, "application/json", json.dumps(data).encode("utf-8"))

    def _read_body(self) -> str:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length).decode("utf-8")

    def _bearer_subject(self) -> Optional[str]:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        return verify_jwt(auth[len("Bearer "):])

    # --- pages ---

    def _login_page(self) -> None:
        html = """<!DOCTYPE html>
<html>
<head><title>JWT CRUD Test App</title></head>
<body>
  <form action="/api/login" method="POST">
    <input id="username" name="username" type="text" />
    <input id="password" name="password" type="password" />
    <button id="submit-btn" type="submit">Sign In</button>
  </form>
</body>
</html>"""
        self._send(200, "text/html", html.encode("utf-8"))

    def _dashboard_page(self, sub: str, token: str) -> None:
        html = f"""<!DOCTYPE html>
<html>
<body>
  <div id="dashboard" data-token="{token}"><h1>Welcome {sub}</h1></div>
</body>
</html>"""
        self._send(200, "text/html", html.encode("utf-8"))

    # --- HTTP verbs ---

    def do_GET(self):
        if self.path == "/login":
            self._login_page()
        elif self.path == "/assets/app.css":
            # Static asset noise: must be filtered out of the dump.
            self._send(200, "text/css", "body { font-family: sans-serif; }".encode("utf-8"))
        elif self.path == "/api/items":
            sub = self._bearer_subject()
            if sub is None:
                self._send_json(401, {"error": "unauthorized"})
                return
            items = _ITEMS.get(sub, [])
            self._send_json(200, {"items": items})
        elif self.path.startswith("/api/items/"):
            sub = self._bearer_subject()
            if sub is None:
                self._send_json(401, {"error": "unauthorized"})
                return
            item_id = self.path.rsplit("/", 1)[1]
            items = _ITEMS.get(sub, [])
            item = next((i for i in items if i["id"] == item_id), None)
            if item is None:
                self._send_json(404, {"error": "not found"})
            else:
                self._send_json(200, item)
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/api/login":
            body = parse_qs(self._read_body())
            username = (body.get("username") or [""])[0]
            password = (body.get("password") or [""])[0]
            if VALID_CREDENTIALS.get(username) != password:
                self._send_json(401, {"error": "invalid credentials"})
                return
            token = make_jwt(username)
            _ITEMS.setdefault(username, [])
            self._dashboard_page(username, token)
        elif self.path == "/analytics/track":
            # Tracking noise: must be filtered out of the dump.
            self._send_json(200, {"ok": True})
        elif self.path == "/api/items":
            sub = self._bearer_subject()
            if sub is None:
                self._send_json(401, {"error": "unauthorized"})
                return
            payload = json.loads(self._read_body() or "{}")
            item = {"id": f"item_{len(_ITEMS[sub]) + 1}", **payload}
            _ITEMS[sub].append(item)
            self._send_json(201, item)
        else:
            self._send_json(404, {"error": "not found"})

    def do_DELETE(self):
        if self.path.startswith("/api/items/"):
            sub = self._bearer_subject()
            if sub is None:
                self._send_json(401, {"error": "unauthorized"})
                return
            item_id = self.path.rsplit("/", 1)[1]
            items = _ITEMS.get(sub, [])
            remaining = [i for i in items if i["id"] != item_id]
            if len(remaining) == len(items):
                self._send_json(404, {"error": "not found"})
                return
            _ITEMS[sub] = remaining
            self._send_json(200, {"deleted": item_id})
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, format, *args):
        """Silence HTTP request logs during testing."""
        pass


# In-memory item store, keyed by username, shared across requests.
_ITEMS: Dict[str, list] = {}


def start_jwt_crud_app(host: str = "127.0.0.1"):
    """Start the JWT CRUD app on a random free port; return (server, port)."""
    server = HTTPServer((host, 0), JWTCrudApp)
    port = server.server_address[1]
    return server, port
