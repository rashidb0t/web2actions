"""
Auth-session loading for `web2actions serve` (Module 18 / Option A).

The MCP runtime can inject authentication per tool call. This module loads a
self-hoster's locally-saved auth session from a JSON file and exposes it as an
`auth_provider` callable, so `serve` can authenticate against protected apps.

The auth file is a simple JSON, e.g.:
    {"token": "my-bearer-token"}
or:
    {"cookies": {"sessionid": "abc123", "CSRF": "xyz"}}
or both.

Secrets stay in the auth file (chmod 600), never in the connector definition or
logs. The connector definition itself remains auth-free.
"""

import json
import os
from typing import Any, Callable, Dict, Optional


def load_auth_file(path: str) -> Dict[str, Any]:
    """Read and validate an auth JSON file. Raises if missing/invalid."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Auth file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Auth file must be a JSON object: {path}")
    # Accept at least one recognized key.
    if not any(k in data for k in ("token", "cookies")):
        raise ValueError(
            f"Auth file must contain 'token' and/or 'cookies': {path}"
        )
    return data


def auth_provider_from_file(path: str) -> Callable[[], Dict[str, Any]]:
    """
    Build an auth_provider callable that reads the auth file fresh on each call.

    Returning a callable (not the static dict) means the MCP server can re-read
    the file — useful if a self-hoster rotates the session without restarting.
    """
    loaded = load_auth_file(path)

    def provider() -> Dict[str, Any]:
        # Re-read so external rotation of the file takes effect.
        return loaded

    return provider


def headers_from_auth(auth: Dict[str, Any]) -> Dict[str, str]:
    """Convert an auth dict into HTTP headers for a request."""
    headers: Dict[str, str] = {}
    token = auth.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    cookies = auth.get("cookies")
    if cookies:
        if isinstance(cookies, dict):
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        else:
            cookie_str = str(cookies)
        headers["Cookie"] = cookie_str
    return headers