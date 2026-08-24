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

### `model` — choose your LLM provider and model (persisted)

```bash
web2actions model                       # show current
web2actions model google/gemini-2.5-flash   # set default model (persisted)
web2actions model --provider openrouter # set default provider
web2actions model --alias sonnet=anthropic/claude-sonnet-4  # alias
web2actions model --aliases             # list aliases
```

### `analyze` — discover a site's API surface (agent harness)

Runs the agent over captured traffic and lists the meaningful API endpoints
(using your configured LLM — any provider via litellm). It reverse-engineers
**almost any** backend — a custom REST API, GraphQL, SDK/RPC protocols,
form-based server actions, or a backend on a completely different domain
(like Supabase) — by analyzing the real traffic rather than assuming a shape:

```bash
web2actions capture https://app.example.com          # produces traffic.json
web2actions analyze traffic.json
```

You can pick a model with `--model`, or it uses your saved `web2actions model`
choice.

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

Web2Actions uses **litellm**, which connects to 100+ providers through one
OpenAI-compatible interface. You pick a provider and a model with simple
commands — no code changes, and the choice is remembered for future runs.

### Supported providers

litellm supports 100+ providers, including **OpenAI, Anthropic, Google
Gemini, OpenRouter, DeepSeek, Groq, xAI, Mistral, OpenAI-compatible local
servers (Ollama / llama.cpp / vLLM), Bedrock, Azure, and more.**

Each provider reads its standard API-key environment variable (for example
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`,
`DEEPSEEK_API_KEY`, `GROQ_API_KEY`, `XAI_API_KEY`) or, for local servers,
needs no key at all.

### Set the default model with a simple command

```bash
# Pick a provider + model once; it is remembered (saved to ~/.web2actions/config.toml)
web2actions model openai/gpt-4o-mini
web2actions model anthropic/claude-sonnet-4
web2actions model gemini/gemini-2.5-flash
web2actions model openrouter/anthropic/claude-sonnet-4
web2actions model deepseek/deepseek-chat

# Show the current model
web2actions model

# Set a default provider
web2actions model --provider openrouter

# Add a short alias, then use it anywhere
web2actions model --alias sonnet=anthropic/claude-sonnet-4
web2actions generate dump.json --model sonnet

# List your aliases
web2actions model --aliases
```

Once set, `generate` uses that model automatically:

```bash
web2actions model google/gemini-2.5-flash
export GEMINI_API_KEY=...            # only needed the first time, per provider
web2actions generate dump.json       # uses gemini-2.5-flash
```

### Override per run

Pass `--model` to use a different provider/model for a single command, or set
the `WEB2ACTIONS_MODEL` env var. Precedence: `--model` > `WEB2ACTIONS_MODEL` >
saved config.

```bash
web2actions generate dump.json --model openai/gpt-4o-mini
```

### If no key is set

`generate` fails gracefully and tells you which key to set — it never crashes
with a raw stack trace.

## Repository layout

- `connector-spec/` — the connector definition schema + validator
- `capture/` — browser session + traffic recording + noise filtering
- `generate/` — LLM extraction (cheap path) + sandboxed fallback
- `validate/` — live tool smoke tests + risk tagging
- `mcp-runtime/` — the shared MCP server that serves any connector
- `agent/` — the agent harness (vendored CLI-Anything-Web) + provider-agnostic LLM backend
- `cli/` — the `web2actions` command-line wrapper

## License

Apache-2.0. Built on top of the open-source CLI-Anything / CLI-Anything-Web
projects.