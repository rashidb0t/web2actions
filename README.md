# Web2Actions

**Turn any website into an MCP server your AI agent can use — no API required.**

Almost every website has data and actions, but few expose a clean public API.
Web2Actions watches a site's browser traffic, reverse-engineers its real
endpoints, and packages them into named tools your AI agent can call over
[Model Context Protocol (MCP)](https://modelcontextprotocol.io) — the open
standard for connecting agents to tools.

## Concepts

- **Connector** — a JSON file describing a website's capabilities as a list of
  tools (name, what it does, its inputs, its risk level, and the HTTP call
  behind it). This is the artifact Web2Actions produces and everything else
  operates on.
- **MCP server** — the thing that exposes a connector's tools to an AI agent.
  Web2Actions serves any connector as a standard MCP server, so your agent can
  call the site's tools like any other tool.
- **Capture** — the one step where a human is involved. A real browser opens;
  *you* log in and use the site as you normally would, and Web2Actions records
  the network traffic. It never guesses buttons or clicks for you.
- **Agent** — an LLM (your choice of provider) that reads the captured traffic
  and reverse-engineers it into a connector.

> **Not supported:** MFA / CAPTCHA / anti-bot challenges. If a site requires
> those, Web2Actions detects it and stops with a clear message rather than
> producing a broken connector.

## Install

```bash
pip install -e .
playwright install chromium      # downloads the browser used by `capture`
```

## The full flow (90 seconds)

```bash
# 1. Model — one-time, saves your choice (see "LLM providers" below)
web2actions model gemini/gemini-2.5-flash

# 2. Capture — opens a browser; log in + use the site, then press Enter
web2actions capture https://app.example.com -o traffic.json

# 3. Analyze — an LLM turns the traffic into a connector (one tool per page/endpoint)
web2actions analyze traffic.json --url https://app.example.com -o connector.json

# 4. Validate + Serve — check it, then expose as MCP
web2actions validate connector.json
web2actions serve connector.json
```

That's it. After step 4, point your AI agent's MCP client at the server and the
site's tools are callable.

## Commands

### `model` — choose your LLM

```bash
web2actions model                      # show the current model
web2actions model gemini/gemini-2.5-flash   # set & remember a model (one-time)
```
See [LLM providers](#llm-providers) for how models/providers work.

### `capture` — record a site's traffic

```bash
web2actions capture https://app.example.com -o traffic.json
```
Opens a browser. Log in, use the site, then press Enter in the terminal. Traffic
is saved to `traffic.json`.

### `analyze` — traffic → connector

```bash
web2actions analyze traffic.json --url https://app.example.com -o connector.json
```
The agent reads the traffic and writes a connector — one tool per page/endpoint
you visited. Add `--assume` to skip the clarifying questions it may ask.

### `validate` — check a connector

```bash
web2actions validate connector.json     # -> VALID
```

### `serve` — expose a connector as MCP

```bash
web2actions serve connector.json
```
Serves over stdio. **Authenticated apps:** pass a local auth session so tool
calls are authenticated:

```bash
# auth.json — {"token": "..."} and/or {"cookies": {"sessionid": "abc"}}
web2actions serve connector.json --auth auth.json
```
Keep `auth.json` local with `chmod 600` — it never goes into the connector or logs.

### Start without capturing (try an example)

```bash
web2actions validate connector-spec/examples/simple-crm.json
web2actions serve connector-spec/examples/simple-crm.json
```

## LLM providers

Web2Actions uses **litellm**, which talks to 100+ providers through one
interface. You only ever set a model once with `web2actions model`; everything
else uses it.

Supported: **OpenAI, Anthropic, Google Gemini, OpenRouter, DeepSeek, Groq, xAI,
Mistral, and local servers (Ollama / llama.cpp / vLLM)**.

```bash
# Set any provider + model (the prefix = provider, the rest = model)
web2actions model openai/gpt-4o-mini
web2actions model anthropic/claude-sonnet-4
web2actions model gemini/gemini-2.5-flash
web2actions model openrouter/anthropic/claude-sonnet-4
web2actions model deepseek/deepseek-chat

# Use a local model (no API key)
web2actions model ollama/llama3
```

**API keys:** each cloud provider reads its standard environment variable —
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`,
etc. Local servers (Ollama/llama.cpp) need no key. Export the key for the
provider you use:

```bash
export GEMINI_API_KEY="your-key"
```

**Override for one command:** pass `--model` to use a different model just for
that run:
```bash
web2actions analyze traffic.json --model openai/gpt-4o-mini
```

## How it works under the hood

1. **Capture** records every request the browser makes while you use the site —
   across any domain (a site's real API may live on a separate host, e.g. a
   Supabase backend).
2. **Analyze** sends that traffic to your LLM, which picks out the real
   data-loading calls and names them as tools — one per page/endpoint. It works
   for almost any backend (REST, GraphQL, form-based, server-rendered pages).
3. **Validate** checks the connector against our schema (names, methods, risk).
4. **Serve** runs it as an MCP server, so an agent can call the site's tools.

Works for almost any website — custom REST APIs, GraphQL, Supabase-backed apps,
form-based apps, server-rendered pages. Sites behind MFA/CAPTCHA are refused
with a clear message.

## Repository layout

- `connector-spec/` — the connector schema + validator
- `capture/` — browser session, traffic recorder, noise filter, auth file
- `agent/` — the reverse-engineering harness + provider-agnostic LLM backend
- `generate/` — (legacy) LLM extraction
- `validate/` — live tool smoke tests + risk tagging
- `mcp-runtime/` — the MCP server that serves any connector
- `cli/` — the `web2actions` command

## License

Apache-2.0. Built on top of the open-source [CLI-Anything](https://github.com/HKUDS/CLI-Anything)
and [CLI-Anything-Web](https://github.com/ItamarZand88/CLI-Anything-WEB) projects.
