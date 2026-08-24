"""
Turn a discovered API surface into a connector-definition JSON (Module 17 / STORY-17.3).

The analyze step reports the API endpoints a web app really calls. This module
turns those endpoints into a valid connector definition that passes the module 1
connector-spec validation and can be served via mcp-runtime.

Generality: it accepts endpoints for ANY backend and emits tools from them; it
does not assume a specific API shape.
"""

import os
import re
import sys
from typing import Any, Dict, List, Optional

from urllib.parse import urlparse

_SIBLING = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "connector-spec"))
if _SIBLING not in sys.path:
    sys.path.insert(0, _SIBLING)
from validate import validate_connector  # noqa: E402

_RISK_BY_METHOD = {
    "GET": "read",
    "POST": "write",
    "PUT": "write",
    "PATCH": "write",
    "DELETE": "destructive",
}


def _tool_name(url: str, index: int) -> str:
    """Derive a schema-valid tool name (starts with letter, alnum only)."""
    path = urlparse(url).path
    parts = [p for p in path.split("/") if p and not p.isdigit()]
    base = re.sub("[^a-zA-Z0-9]", "", parts[-1]).lower() if parts else ""
    if not base:
        base = "resource"
    if not base[0].isalpha():
        base = "resource" + base
    return f"{base}{index}"


def _camelize(name: str) -> str:
    """Convert snake_case/kebab to camelCase and drop non-alnum, e.g.
    view_dashboard -> viewDashboard, list-tasks -> listTasks. Guarantees the
    schema's '^[a-zA-Z][a-zA-Z0-9]*$'."""
    import re as _re
    cleaned = _re.sub("[^a-zA-Z0-9]+", " ", name)
    words = [w for w in cleaned.split(" ") if w]
    if not words:
        return "tool"
    first = words[0][0].lower() + words[0][1:] if words[0] else "tool"
    rest = "".join(w[0].upper() + w[1:] for w in words[1:] if w)
    result = first + rest
    return result or "tool"


def _endpoint_to_tool(endpoint: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Turn one discovered endpoint into a connector tool definition."""
    method = (endpoint.get("method") or "GET").upper()
    if method not in _RISK_BY_METHOD:
        method = "GET"
    url = endpoint.get("url", "")
    raw_name = endpoint.get("name") or _tool_name(url, index)
    name = _camelize(raw_name)
    return {
        "name": name,
        "description": endpoint.get("purpose") or endpoint.get("name") or name,
        "risk": _RISK_BY_METHOD[method],
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "outputSchema": {"type": "object", "properties": {}},
        "call": {"method": method, "url": url, "headers": {}, "body": {}},
    }


def build_connector(
    endpoints: List[Dict[str, Any]],
    name: str,
    website_url: str,
    auth_type: str = "none",
) -> dict:
    """Build + validate a connector definition from a discovered API surface."""
    tools = [_endpoint_to_tool(e, i) for i, e in enumerate(endpoints) if e.get("url")]
    connector = {
        "name": name,
        "version": "1.0.0",
        "description": f"Connector for {website_url}",
        "websiteUrl": website_url,
        "auth": {"type": auth_type},
        "tools": tools,
    }
    ok, error = validate_connector(connector)
    if not ok:
        raise ValueError(f"Generated connector invalid: {error}")
    return connector


def _method_in_line(line: str) -> str:
    """Return the HTTP verb token present in a line, else GET.

    Handles 'POST https://...', '**Method:** `POST`', and bare 'POST'.
    """
    m = re.search("([A-Z]{3,7})", line)
    if m:
        verb = m.group(1).upper()
        if verb in _RISK_BY_METHOD:
            return verb
    return "GET"


def _name_in_line(line: str) -> Optional[str]:
    """Extract a clean Name token from a report line, or None.

    Handles Gemini markdown blocks ('**Name:** view_dashboard') and inline
    ('Name: view_dashboard'). Uses string ops to avoid backslash escapes.
    """
    idx = line.find("Name")
    if idx < 0:
        return None
    rest = line[idx + 4:]
    # skip any asterisks/spaces/quotes/markdown
    rest = rest.lstrip("* :`")
    import re as _re
    m = _re.match("[A-Za-z][A-Za-z0-9_]*", rest)
    if m:
        return m.group(0)[:63]
    return None


def parse_report(report: str) -> List[Dict[str, Any]]:
    """Tolerantly parse the analyze report into endpoint dicts (url, method, name).

    One (method, url) pair per line; duplicated URLs stay distinct. Name is
    looked up on nearby lines for Gemini's multi-line block format.
    """
    lines = report.splitlines()
    endpoints = []
    for i, line in enumerate(lines):
        m = re.search("https?://[^\\s\\),]+", line)
        if not m:
            continue
        url = m.group(0).rstrip(".")
        ep = {"url": url, "method": _method_in_line(line)}
        # look for a Name on this line or the next few lines
        window = lines[i:i + 3]
        for wl in window:
            n = _name_in_line(wl)
            if n:
                ep["name"] = n
                break
        endpoints.append(ep)
    return endpoints