# Web2Actions

**Turn a website into an MCP server your AI agent can use — no API required.**

Web2Actions watches a website's browser traffic, reverse-engineers the site's
real network endpoints, and packages them into a clean set of named tools your
AI agent can call via [Model Context Protocol (MCP)](https://modelcontextprotocol.io).
No public API required.

## How it works

1. **Capture** — log into a site once; the browser traffic is recorded.
2. **Generate** — an LLM turns the captured traffic into a connector definition:
   clean named tools with inputs, outputs, and risk tags.
3. **Validate** — every tool is smoke-tested against the live site.
4. **Serve** — the validated connector is exposed as a standard MCP server.

> **Capture is human-driven, not automatic.** We don't guess every button or
> click the site for you. A real browser opens on your machine; *you* log in and
> perform the actions you want turned into tools, and we record that traffic.
> The same philosophy applies in the hosted product — it's a popup browser you
> drive. The CLI just runs that browser for you.

## Install

```bash
pip install -e .
```

## Commands

Every command is `web2actions <command> [options]`.

### `capture` — record a site's traffic

Opens a browser to the URL, records the network traffic you generate as you
log in and click, then writes a JSON dump.

```bash
# Open the site; log in and click around manually; press Enter when done.
web2actions capture https://app.example.com

# Filter out analytics/static noise and save to a chosen file.
web2actions capture https://app.example.com --filter -o dump.json

# Automate a simple form login (fill + submit), then continue capturing.
web2actions capture https://app.example.com --login \
  --username you@example.com --password "..." \
  --username-selector "#username" --password-selector "#password" \
  --submit-selector "#submit-btn" --success-indicator "#dashboard"
```

Options: `--login`, `--username`, `--password`, `--username-selector`,
`--password-selector`, `--submit-selector`, `--success-indicator`,
`--filter`, `--output/-o`.

### `generate` — turn captured traffic into a connector definition

```bash
web2actions generate dump.json --model claude-sonnet-4 -o connector.json
```

Options: `--model` (or `WEB2ACTIONS_MODEL` env), `--output/-o`.

### `validate` — check a connector against the schema

```bash
web2actions validate connector.json
# -> VALID
```

### `serve` — expose a connector as an MCP server (stdio)

```bash
web2actions serve connector.json
```

Wires the connector to your AI agent's MCP client over stdio.

### End-to-end example

```bash
web2actions capture https://example.com --filter -o dump.json
web2actions generate dump.json --model claude-sonnet-4 -o connector.json
web2actions validate connector.json
web2actions serve connector.json
```

### Start from an existing example (no capture needed)

```bash
web2actions validate connector-spec/examples/simple-crm.json
web2actions serve connector-spec/examples/simple-crm.json
```

## Bringing your own LLM (BYOK)

Generation uses whatever LLM you point it at. Web2Actions never stores a key
inside the project — you supply your own, chosen at runtime per invocation.

### Supported providers

The `generate` step is provider-agnostic. It can call:

- **Cloud models**
  - **OpenAI** — set `OPENAI_API_KEY`
  - **Anthropic** — set `ANTHROPIC_API_KEY`
- **Local models (free, no API key)**
  - **Ollama** — run `ollama serve`, then use a model like `llama3` or `qwen2.5`
  - **llama.cpp** — point it at a local GGUF model server

### 1. Add an API key (environment variable)

Export the key for the provider you want in your shell (or your `~/.bashrc` /
`~/.zshrc` so it persists):

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 2. Pick a provider + model

Models are selected by name. To explicitly route to a provider, prefix the
model with the provider and a slash (`provider/model`). If you give a bare
model name with no prefix, the provider is **auto-detected** (local providers
first, then cloud), using whichever is available.

```bash
# Aim at a specific provider with `provider/model`:
web2actions generate dump.json --model openai/gpt-4o-mini      # OpenAI
web2actions generate dump.json --model anthropic/claude-sonnet-4  # Anthropic
web2actions generate dump.json --model ollama/llama3           # local (Ollama)

# Bare model name: provider is auto-detected from what's available
web2actions generate dump.json --model gpt-4o-mini
```

You can also set the default model once via the `WEB2ACTIONS_MODEL` env var,
so you don't have to pass `--model` every time:

```bash
export WEB2ACTIONS_MODEL="claude-sonnet-4"
web2actions generate dump.json        # uses claude-sonnet-4
```

### Switching providers

Changes the model name and (for cloud) ensures the matching API key is set.
No code or config file changes needed:

```bash
# Same command, different provider, via the provider/model prefix:
web2actions generate dump.json --model openai/gpt-4o-mini        # OpenAI
web2actions generate dump.json --model anthropic/claude-sonnet-4 # Anthropic
web2actions generate dump.json --model ollama/llama3             # local, free
```

Precedence: an explicit `--model` flag wins over `WEB2ACTIONS_MODEL`.

### If no key is set

`generate` fails gracefully and tells you what to do — set a cloud key or run
a local model server. It never crashes with a stack trace.

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