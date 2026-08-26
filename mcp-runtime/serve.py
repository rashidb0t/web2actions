"""
Shared MCP runtime for Web2Actions (module 7).

One program serves ANY valid connector definition as an MCP server. There is
no per-connector code generation — the same code registers the connector's
tools dynamically and executes each tool's `call` spec at invocation time.

Exposes the standard MCP `tools/list` and `tools/call` methods.

Security contract:
- Egress is restricted to the connector's declared `websiteUrl` host (SSRF
  guard). No tool call can reach a host outside that allow-list.
- Tool arguments are validated against each tool's `inputSchema`.
- A bearer token is never stored here. Callers (e.g. the private gateway)
  supply it via `auth_provider`, keeping credentials out of this repo.
"""

from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

import jsonschema
import requests
from mcp.server.lowlevel import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio as stdio
import mcp.types as types

#: Maximum size (bytes) of a response body read back to the client.
_MAX_RESPONSE_BYTES = 100_000


def _tool_from_connector(tool: Dict[str, Any]) -> types.Tool:
    """Map one connector tool dict to an MCP Tool object."""
    return types.Tool(
        name=tool["name"],
        description=tool.get("description", ""),
        input_schema=tool.get("inputSchema", {"type": "object", "properties": {}}),
    )


def _allowed_hosts(connector: Dict[str, Any]) -> List[str]:
    """Return the list of hostnames a connector's tools may call."""
    hosts = []
    website_url = connector.get("websiteUrl", "")
    if website_url:
        hosts.append(urlparse(website_url).hostname or "")
    return [h for h in hosts if h]


def _validate_url(url: str, allowed_hosts: List[str]) -> None:
    """Raise if the request URL host is not in the allowed list (SSRF guard)."""
    host = urlparse(url).hostname or ""
    if not allowed_hosts or host not in allowed_hosts:
        raise ValueError(f"Refusing to call host not in connector allow-list: {host}")


def _validate_arguments(tool: Dict[str, Any], arguments: Dict[str, Any]) -> None:
    """Validate tool arguments against the tool's inputSchema."""
    schema = tool.get("inputSchema") or {"type": "object", "properties": {}}
    try:
        jsonschema.validate(instance=arguments or {}, schema=schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(f"Arguments failed validation: {exc.message}")


def _build_headers(
    call_spec: Dict[str, Any],
    token: Optional[str] = None,
    auth: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Assemble HTTP request headers from call_spec + auth token/cookies."""
    headers = dict(call_spec.get("headers") or {})
    if token:
        headers.setdefault("Authorization", f"Bearer {token}")
    if auth:
        for k, v in auth.items():
            if k == "token" and v:
                headers.setdefault("Authorization", f"Bearer {v}")
            elif k == "cookies" and v:
                if isinstance(v, dict):
                    headers.setdefault("Cookie", "; ".join(f"{ck}={cv}" for ck, cv in v.items()))
                else:
                    headers.setdefault("Cookie", str(v))
    return headers


def _execute_call(
    call_spec: Dict[str, Any],
    arguments: Dict[str, Any],
    token: Optional[str] = None,
    allowed_hosts: Optional[List[str]] = None,
    auth: Optional[Dict[str, Any]] = None,
    on_auth_expired: Optional[Callable[[], Optional[Dict[str, Any]]]] = None,
) -> str:
    """Execute a tool's HTTP call spec and return the response as text.

    `token` (a bearer token, legacy) and/or `auth` (a dict with 'token' and/or
    'cookies') can be supplied to authenticate the request.

    On 401/403 (unauthorized/forbidden), if `on_auth_expired` is provided,
    triggers a re-auth / token refresh and retries the call once before failing.
    """
    method = call_spec.get("method", "GET").upper()
    url = call_spec["url"]
    headers = _build_headers(call_spec, token=token, auth=auth)
    body = call_spec.get("body")

    # Allow {param} placeholders in the URL to be filled from arguments.
    for key, value in (arguments or {}).items():
        url = url.replace("{" + key + "}", str(value))

    _validate_url(url, allowed_hosts or [])

    response = requests.request(
        method, url, headers=headers, json=body if body is not None else None, timeout=15
    )

    # Auto re-auth on 401/403 expiry if re-auth handler is configured
    if response.status_code in (401, 403) and on_auth_expired is not None:
        try:
            fresh_auth = on_auth_expired()
            if fresh_auth:
                headers = _build_headers(call_spec, auth=fresh_auth)
                response = requests.request(
                    method, url, headers=headers, json=body if body is not None else None, timeout=15
                )
        except Exception:
            pass

    text = response.text
    if len(text.encode("utf-8")) > _MAX_RESPONSE_BYTES:
        text = text[:_MAX_RESPONSE_BYTES] + "\n...[truncated]"
    return text


def build_server(
    connector: Dict[str, Any],
    auth_provider: Optional[Callable[[], Optional[Any]]] = None,
    on_auth_expired: Optional[Callable[[], Optional[Dict[str, Any]]]] = None,
) -> Server:
    """Build an MCP Server serving the given connector definition.

    `auth_provider` is an optional zero-arg callable, invoked per tool call,
    returning an auth dict ('token' and/or 'cookies') — or a legacy bearer
    token string — or None. Credentials are fetched fresh and never stored in
    this module, keeping the public repo free of secrets.

    `on_auth_expired` is an optional zero-arg callable triggered on 401/403
    HTTP responses to refresh/re-login and retry the request.
    """
    tools = {t["name"]: t for t in connector.get("tools", [])}
    allowed_hosts = _allowed_hosts(connector)

    # Derive on_auth_expired from auth_provider if auth_provider has a reauth attribute
    reauth_handler = on_auth_expired
    if reauth_handler is None and hasattr(auth_provider, "reauth"):
        reauth_handler = getattr(auth_provider, "reauth")

    async def on_list_tools(_ctx, _params):
        return types.ListToolsResult(tools=[_tool_from_connector(t) for t in tools.values()])

    async def on_call_tool(_ctx, params):
        name = params.name
        arguments = params.arguments or {}
        tool = tools.get(name)
        if tool is None:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Unknown tool: {name}")],
                is_error=True,
            )
        try:
            _validate_arguments(tool, arguments)
            auth = auth_provider() if auth_provider else None
            if isinstance(auth, str):  # legacy: bare bearer token
                auth = {"token": auth}
            result_text = _execute_call(
                tool.get("call", {}),
                arguments,
                allowed_hosts=allowed_hosts,
                auth=auth,
                on_auth_expired=reauth_handler,
            )
            return types.CallToolResult(content=[types.TextContent(type="text", text=result_text)])
        except ValueError as exc:
            # Validation/allow-list errors are safe to surface; no internals.
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=str(exc))], is_error=True
            )
        except Exception:  # noqa: BLE001 - never leak internals to the client
            return types.CallToolResult(
                content=[types.TextContent(type="text", text="Tool call failed")], is_error=True
            )

    return Server(
        "web2actions-connector",
        version="0.1.0",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


async def run_stdio(
    connector: Dict[str, Any],
    auth_provider: Optional[Callable[[], Optional[str]]] = None,
) -> None:
    """Serve a connector definition over stdio for an MCP stdio client."""
    server = build_server(connector, auth_provider=auth_provider)
    async with stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="web2actions-connector",
                server_version="0.1.0",
                capabilities=server.get_capabilities(),
            ),
        )