# Web2Actions

**Turn a website into an MCP server your AI agent can use — no API required.**

Web2Actions watches a website's browser traffic, reverse-engineers the site's
real network endpoints, and packages them into a clean set of named tools your
AI agent can call via [Model Context Protocol (MCP)](https://modelcontextprotocol.io).
No public API required.

## How it works

1. **Capture** — log into a site once; we record the browser's network traffic.
2. **Generate** — an LLM turns the captured traffic into a connector definition:
   clean named tools with inputs, outputs, and risk tags.
3. **Validate** — every tool is smoke-tested against the live site.
4. **Serve** — the validated connector is exposed as a standard MCP server.

## Quickstart

```bash
# Install (from this repo) and add your LLM key
pip install -e .
export ANTHROPIC_API_KEY=...   # or OPENAI_API_KEY / GEMINI_API_KEY

# Generate a connector definition from captured traffic
web2actions generate traffic.json --model claude-sonnet-4 -o connector.json

# Validate it against the connector schema
web2actions validate connector.json

# Serve it as an MCP server an AI agent can use
web2actions serve connector.json
```

### Start from an existing example (no capture needed)

```bash
web2actions validate connector-spec/examples/simple-crm.json
web2actions serve connector-spec/examples/simple-crm.json
```

## Bringing your own LLM (BYOK)

Generation uses whatever LLM you point it at. Set a cloud API key
(`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, ...) or run a local
model server (Ollama / llama.cpp). Pick the model with `--model` or the
`WEB2ACTIONS_MODEL` env var. No key is stored in or bundled with this project.

## Repository layout

- `connector-spec/` — the connector definition schema + validator
- `capture/` — browser session + traffic recording + noise filtering
- `generate/` — LLM extraction (cheap path) + sandboxed fallback
- `validate/` — live tool smoke tests + risk tagging
- `mcp-runtime/` — the shared MCP server that serves any connector
- `cli/` — the `web2actions` command-line wrapper

## License

Apache-2.0. Built on top of the open-source CLI-Anything / CLI-Anything-Web
projects.