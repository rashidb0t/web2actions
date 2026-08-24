"""
Live tool smoke test for Web2Actions (Validate, module 5).

Replays every tool in a connector definition once against a live target site,
records whether each call succeeded (no transport/http error), and flags
broken tools without blocking the others. This is a smoke test — it confirms
the connector's tool calls actually work against the real backend.
"""

from typing import Any, Dict, List, Optional


def _build_headers(
    tool: Dict[str, Any],
    token: Optional[str],
) -> Dict[str, str]:
    """Build request headers from the tool's call spec + optional bearer token."""
    headers = dict(tool.get("call", {}).get("headers") or {})
    if token:
        headers.setdefault("Authorization", f"Bearer {token}")
    return headers


def call_tool(
    tool: Dict[str, Any],
    base_url: str,
    token: Optional[str] = None,
    input_values: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Execute one tool's HTTP call against the live target.
    Returns {"tool": name, "ok": bool, "status": int|None, "error": str|None}.
    A transport or HTTP error marks the tool as failed, but never raises.
    """
    call_spec = tool.get("call", {})
    method = call_spec.get("method", "GET").upper()
    url = call_spec["url"]
    # Allow the URL to reference base_url placeholder.
    url = url.replace("{base_url}", base_url)

    header_map = _build_headers(tool, token)
    expected_status = 200

    try:
        from requests import request

        response = request(method, url, headers=header_map, timeout=10)
        ok = response.status_code == expected_status or response.status_code < 400
        return {
            "tool": tool.get("name"),
            "ok": ok,
            "status": response.status_code,
            "error": None if ok else f"HTTP {response.status_code}",
        }
    except Exception as exc:  # noqa: BLE001 - a network failure flags the tool, doesn't crash the run
        return {"tool": tool.get("name"), "ok": False, "status": None, "error": str(exc)}


def smoke_test_connector(
    connector: Dict[str, Any],
    base_url: str,
    token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Run every tool in the connector against the live target once.
    Returns a list of per-tool results. A broken tool is flagged in its own
    entry and does not stop the remaining tools from being tested.
    """
    results = []
    for tool in connector.get("tools", []):
        result = call_tool(tool, base_url, token)
        results.append(result)
    return results