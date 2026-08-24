"""
Shared MCP runtime for Web2Actions (module 7).

One program serves ANY valid connector definition as an MCP server. There is
no per-connector code generation — the same code registers the connector's
tools dynamically and executes each tool's `call` spec at invocation time.

Exposes the standard MCP `tools/list` and `tools/call` methods.
"""

from typing import Any, Dict, List

import requests
from mcp.server.lowlevel import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio as stdio
import mcp.types as types


def _tool_from_connector(tool: Dict[str, Any]) -> types.Tool:
    """Map one connector tool dict to an MCP Tool object."""
    return types.Tool(
        name=tool["name"],
        description=tool.get("description", ""),
        input_schema=tool.get("inputSchema", {"type": "object", "properties": {}}),
    )


def _execute_call(
    call_spec: Dict[str, Any],
    arguments: Dict[str, Any],
    token: str | None = None,
) -> str:
    """Execute a tool's HTTP call spec and return the response as text."""
    method = call_spec.get("method", "GET").upper()
    url = call_spec["url"]
    headers = dict(call_spec.get("headers") or {})
    if token:
        headers.setdefault("Authorization", f"Bearer {token}")
    body = call_spec.get("body")

    # Allow {param} placeholders in the URL to be filled from arguments.
    for key, value in (arguments or {}).items():
        url = url.replace("{" + key + "}", str(value))

    response = requests.request(
        method, url, headers=headers, json=body if body is not None else None, timeout=15
    )
    return response.text


def build_server(connector: Dict[str, Any]) -> Server:
    """Build an MCP Server serving the given connector definition."""
    tools = {t["name"]: t for t in connector.get("tools", [])}

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
            result_text = _execute_call(tool.get("call", {}), arguments)
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=result_text)]
            )
        except Exception as exc:  # noqa: BLE001 - surface the error to the client
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Error: {exc}")],
                is_error=True,
            )

    return Server(
        "web2actions-connector",
        version="0.1.0",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


async def run_stdio(connector: Dict[str, Any]) -> None:
    """Serve a connector definition over stdio for an MCP stdio client."""
    server = build_server(connector)
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