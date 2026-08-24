"""
Turn a discovered API surface into a connector-definition JSON (Module 17 / STORY-17.3).

The analyze step (`cli/agent.py`) reports the API endpoints a web app really
calls. This module turns those endpoints into a valid connector definition that
passes the module 1 connector-spec validation and can be served via
mcp-runtime.

Generality: it accepts endpoints for ANY backend (REST, GraphQL, RPC, form
server-actions, cross-domain hosts) and emits tools from them; it does not
assume a specific API shape. Each endpoint yields a tool whose risk is inferred
mechanically from its HTTP method.
"""

import os
import re
import sys
from typing import Any, Dict, List

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
    """Derive a schema-valid tool name (starts with letter, alnum only).

    The connector-spec requires names matching ^[a-zA-Z][a-zA-Z0-9]*$.
    """
    path = urlparse(url).path
    parts = [p for p in path.split("/") if p and not p.isdigit()]
    base = re.sub(r"[^a-zA-Z0-9]", "", parts[-1]).lower() if parts else ""
    if not base:
        base = "resource"
    if not base[0].isalpha():
        base = "resource" + base
    return f"{base}{index}"


def _endpoint_to_tool(endpoint: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Turn one discovered endpoint into a connector tool definition."""
    method = (endpoint.get("method") or "GET").upper()
    if method not in _RISK_BY_METHOD:
        method = "GET"
    url = endpoint.get("url", "")
    name = endpoint.get("name") or _tool_name(url, index)
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
    """
    Build a connector definition from a discovered API surface (endpoints).

    endpoints: list of dicts with keys url, method, name (optional),
    purpose (optional). Produces tools for ANY backend shape and returns a
    definition that validates against the module 1 schema. Mechanical, no LLM
    needed — always schema-valid if endpoints have URLs.
    """
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
    """Return the HTTP verb token present in a line, else GET."""
    for verb in _RISK_BY_METHOD:
        if re.search(r"\b" + verb + r"\b", line, re.IGNORECASE):
            return verb
    return "GET"


def parse_report(report: str) -> List[Dict[str, Any]]:
    """
    Tolerantly parse the analyze step's textual report into endpoints.

    Each line may look like:
        1. GET https://api.host/v1/customers - read - list customers
        2. [POST] https://... (write)
    One (method, url) pair per line, so duplicated URLs on different lines are
    kept distinct. Lines without a URL are skipped.
    """
    endpoints = []
    for line in report.splitlines():
        m = re.search(r"https?://[^\s\)\],]+", line)
        if not m:
            continue
        url = m.group(0).rstrip(".")
        method = _method_in_line(line)
        endpoints.append({"url": url, "method": method})
    return endpoints