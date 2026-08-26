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
from typing import Any, Callable, Dict, List, Optional


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


def extract_token_from_entries(entries: List[Dict[str, Any]]) -> Optional[str]:
    """Search recorded network requests for Authorization bearer tokens."""
    for entry in entries:
        req = entry.get("request", {})
        headers = req.get("headers", {})
        for k, v in headers.items():
            if k.lower() == "authorization" and isinstance(v, str):
                v_clean = v.strip()
                if v_clean.lower().startswith("bearer "):
                    token = v_clean[7:].strip()
                    if token:
                        return token
                elif v_clean:
                    return v_clean
    return None


def extract_cookies_from_context(context_or_page: Any) -> Dict[str, str]:
    """Extract cookies from a Playwright BrowserContext or Page."""
    cookies_dict: Dict[str, str] = {}
    try:
        if hasattr(context_or_page, "cookies"):
            raw_cookies = context_or_page.cookies()
        elif hasattr(context_or_page, "context") and hasattr(context_or_page.context, "cookies"):
            raw_cookies = context_or_page.context.cookies()
        else:
            raw_cookies = []

        for c in raw_cookies:
            name = c.get("name")
            val = c.get("value")
            if name and val is not None:
                cookies_dict[name] = str(val)
    except Exception:
        pass
    return cookies_dict


def extract_token_from_page(page: Any) -> Optional[str]:
    """Attempt to extract tokens from localStorage/sessionStorage."""
    if not page:
        return None
    try:
        token = page.evaluate("""() => {
            try {
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    const val = localStorage.getItem(key);
                    if (!val) continue;
                    if (key.includes('auth-token') || key.includes('token') || key.includes('jwt') || key.includes('session')) {
                        try {
                            const parsed = JSON.parse(val);
                            if (parsed.access_token) return parsed.access_token;
                            if (parsed.token) return parsed.token;
                            if (parsed.jwt) return parsed.jwt;
                        } catch (e) {}
                        if (typeof val === 'string' && val.length > 20 && !val.includes(' ')) {
                            return val;
                        }
                    }
                }
            } catch (e) {}
            return null;
        }""")
        if token and isinstance(token, str):
            return token.strip()
    except Exception:
        pass
    return None


def extract_session(
    context: Any = None,
    page: Any = None,
    entries: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Extract authentication state (bearer token and/or cookies) from a browser session
    and/or recorded network traffic entries.
    """
    auth: Dict[str, Any] = {}

    # 1. Try extracting token from recorded traffic headers
    if entries:
        token = extract_token_from_entries(entries)
        if token:
            auth["token"] = token

    # 2. Try extracting token from page localStorage if not yet found
    if "token" not in auth and page is not None:
        page_token = extract_token_from_page(page)
        if page_token:
            auth["token"] = page_token

    # 3. Extract cookies from context/page
    target = context or page
    if target is not None:
        cookies = extract_cookies_from_context(target)
        if cookies:
            auth["cookies"] = cookies

    return auth


def save_auth_file(path: str, auth_data: Dict[str, Any]) -> str:
    """Save an auth dictionary to JSON with secure permissions (chmod 600)."""
    if not isinstance(auth_data, dict) or not any(k in auth_data for k in ("token", "cookies")):
        raise ValueError("auth_data must contain 'token' and/or 'cookies'")

    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(auth_data, f, indent=2)

    try:
        os.chmod(path, 0o600)
    except Exception:
        pass

    return path
