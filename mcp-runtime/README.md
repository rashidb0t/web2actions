# MCP Runtime

One shared program that serves ANY valid connector definition as an MCP
server. There is no per-connector code generation — the same code registers
the connector's tools dynamically and executes each tool's `call` spec at
invocation time. Exposes the standard MCP `tools/list` and `tools/call`
methods.

## `serve.py`

- `_tool_from_connector(tool)` — maps a connector tool dict to an MCP `Tool`.
- `_allowed_hosts(connector)` — derives the egress allow-list from the
  connector's `websiteUrl`.
- `_validate_url(url, allowed_hosts)` — SSRF guard: refuses any request whose
  host is not in the connector's allow-list.
- `_validate_arguments(tool, arguments)` — validates tool arguments against
  the tool's `inputSchema` (jsonschema).
- `_execute_call(call_spec, arguments, token=None, allowed_hosts=None)` —
  executes a tool's HTTP call; fills `{param}` placeholders; optional bearer
  token; enforces the SSRF guard; truncates large responses.
- `build_server(connector, auth_provider=None)` — builds an
  `mcp.server.lowlevel.Server`. `auth_provider` is an optional zero-arg
  callable returning a bearer token (fetched fresh per call, never stored).
- `run_stdio(connector, auth_provider=None)` — serves the connector over stdio.

## Security contract

- **SSRF guard:** a tool may only call the host declared in the connector's
  `websiteUrl`. Off-host URLs (e.g. metadata endpoints) are refused.
- **Input schema enforcement:** arguments are validated against each tool's
  `inputSchema` before execution.
- **No credentials stored here:** the public repo never stores credentials.
  Callers (e.g. the private gateway in `web2actions-cloud`) inject a token via
  `auth_provider`, keeping secrets out of the open-core repo (PRD §10, HLA §3).
- **Error sanitization:** internal exception details are never returned to the
  client; only validation/allow-list messages are surfaced.

## `__main__.py`

Run a connector definition as an MCP server over stdio:

```bash
.venv/bin/python -m mcp-runtime <connector-definition.json>
```

## Tests

- `tests/test_serve.py` — integration tests: launches the served connector as
  a stdio subprocess, drives it with a real MCP client session (`stdio_client`
  + `ClientSession`), lists the tool, and invokes it against the live JWT CRUD
  test app. Covers the security contract: SSRF allow-listing, input-schema
  enforcement, authenticated tool calls via token, and error sanitization.

Run with:
```bash
.venv/bin/python -m unittest mcp-runtime.tests.test_serve
```