# MCP Runtime

One shared program that serves ANY valid connector definition as an MCP
server. There is no per-connector code generation — the same code registers
the connector's tools dynamically and executes each tool's `call` spec at
invocation time. Exposes the standard MCP `tools/list` and `tools/call`
methods.

## `serve.py`

- `_tool_from_connector(tool)` — maps a connector tool dict to an MCP `Tool`.
- `_execute_call(call_spec, arguments, token=None)` — executes a tool's HTTP
  call spec against the target; fills `{param}` placeholders from arguments
  and attaches a bearer token when provided.
- `build_server(connector)` — builds an `mcp.server.lowlevel.Server` with
  `tools/list` and `tools/call` handlers driven by the connector definition.
- `run_stdio(connector)` — serves the connector over stdio.

## `__main__.py`

Run a connector definition as an MCP server over stdio:

```bash
.venv/bin/python -m mcp-runtime <connector-definition.json>
```

## Tests

- `tests/test_serve.py` — integration tests: launches the served connector as
  a stdio subprocess, drives it with a real MCP client session (`stdio_client`
  + `ClientSession`), lists the tool, and invokes it against the live JWT CRUD
  test app. Also covers `_tool_from_connector` and `_execute_call`.

Run with:
```bash
.venv/bin/python -m unittest mcp-runtime.tests.test_serve
```