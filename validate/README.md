# Validate Module

Replays every tool in a generated connector once against the live target
site, confirms the call succeeds (no transport or HTTP error), and logs the
result. A deliberately broken tool is flagged without blocking the others.

## `smoke.py`

- `_build_headers(tool, token)` — assembles request headers from the tool's
  call spec, adding a `Bearer` token when provided.
- `call_tool(tool, base_url, token, input_values)` — executes one tool's HTTP
  call; returns `{"tool", "ok", "status", "error"}`. Never raises — a network
  or HTTP failure flags that tool, the run continues.
- `smoke_test_connector(connector, base_url, token)` — runs every tool once,
  collects per-tool results, and flags broken tools individually.

The smoke test runs against a live target (e.g. the JWT CRUD test app in
`capture/tests/jwt_crud_app.py`). Auth is provided externally as a bearer
token obtained from the target's login flow.

## Tests

- `tests/test_smoke.py` — integration test against the live JWT CRUD app:
  all tools replayed, broken-URL tool flagged (404) while the good tool
  passes, and an unauthorized call (no token) flagged as failed.

Run with:
```bash
.venv/bin/python -m unittest validate.tests.test_smoke
```