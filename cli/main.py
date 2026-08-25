"""
Web2Actions command-line interface (module 15, STORY-15.1).

Wraps capture, generate, validate, and the MCP runtime into one local command
with no cloud dependency. Users bring their own LLM API key (BYOK) for the
generate step.

Usage:
    web2actions generate <traffic.json> [--model MODEL] [--output OUT]
    web2actions validate <connector.json>
    web2actions serve <connector.json>
"""

import argparse
import json
import os
import sys
from typing import List, Optional

# Add each open-core package to the import path so sibling imports work.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _pkg in ("connector-spec", "capture", "generate", "validate", "mcp-runtime"):
    _path = os.path.join(_ROOT, _pkg)
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _resolve_model(model: Optional[str]) -> str:
    """Return the model, from --model, WEB2ACTIONS_MODEL env, or the saved config default."""
    if model:
        return model
    env_model = os.environ.get("WEB2ACTIONS_MODEL")
    if env_model:
        return env_model
    try:
        from cli import config
        saved = config.get_model()
        if saved:
            return saved
    except Exception:
        pass
    return "openai/gpt-4o-mini"


def cmd_generate(args: argparse.Namespace) -> int:
    """Run the cheap-path extraction on a traffic dump to produce a connector definition."""
    from extract import run_extraction_job

    with open(args.traffic, "r", encoding="utf-8") as file:
        dump = json.load(file)

    model = _resolve_model(args.model)
    try:
        result = run_extraction_job(dump, model)
    except Exception as exc:  # noqa: BLE001 - surface the BYOK/auth issue cleanly
        print(f"Error running extraction: {exc}")
        print("To use generation, set an LLM API key (e.g. OPENAI_API_KEY, ANTHROPIC_API_KEY) "
              "or run a local model server (Ollama / llama.cpp).")
        return 1

    if result["status"] == "needs_escalation":
        print("Extraction flagged needs_escalation:", result.get("errors"))
        return 1

    connector = result["connector"]
    output = args.output or "connector.json"
    with open(output, "w", encoding="utf-8") as file:
        json.dump(connector, file, indent=2)
    print(f"Wrote connector definition to {output}")
    return 0


def cmd_capture(args: argparse.Namespace) -> int:
    """Open a browser for the user to log in and drive; record its traffic to a dump."""
    from session import BrowserSession
    from recorder import NetworkRecorder

    url = args.url or "about:blank"

    if args.login:
        if not (args.username and args.password):
            print("Login requested: pass --username and --password with --login")
            return 1

    from session import BrowserSession
    from recorder import NetworkRecorder

    session = BrowserSession(headless=False)
    page = session.start()
    recorder = NetworkRecorder()
    recorder.start(page)
    page.goto(url, wait_until="domcontentloaded")

    if args.login:
        from session import perform_login
        perform_login(
            page,
            url,
            args.username_selector or "#username",
            args.username,
            args.password_selector or "#password",
            args.password,
            args.submit_selector or "#submit-btn",
            args.success_indicator,
        )

    print("Browser opened. Log in and perform the actions you want captured.")
    print("When done, press Enter here — the session stays alive and we'll")
    print("auto-visit a few common pages to capture the authenticated data calls,")
    print("then finalize the traffic dump.")
    try:
        input("Press Enter when you're logged in: ")
    except EOFError:
        pass

    # Keep the authenticated session alive; visit candidate data pages so the
    # post-login API calls actually fire and get recorded (the call that was
    # previously lost because we closed immediately on Enter).
    common_pages = (
        "/", "/dashboard", "/home", "/tasks", "/projects", "/kanban",
        "/backlog", "/items", "/data", "/api", "/account",
    )
    visited = 0
    for path in common_pages:
        try:
            page.goto(url.rstrip("/") + path, wait_until="domcontentloaded", timeout=10000)
            page.wait_for_timeout(800)
            visited += 1
        except Exception:
            continue
        if visited >= (args.auto_pages or 6):
            break
    page.wait_for_timeout(1500)

    recorder.stop()
    session.close()

    entries = recorder.get_entries()

    # Refuse if the site is behind MFA / CAPTCHA / anti-bot challenges.
    from agent.guards import CHALLENGE_MESSAGE, detect_challenges
    verdict = detect_challenges(entries)
    if verdict["blocked"]:
        print(CHALLENGE_MESSAGE.format(reasons=", ".join(verdict["reasons"])))
        print("Nothing was written.")
        return 1

    if args.filter and url != "about:blank":
        from filter import filter_traffic
        # Keep API calls from ANY domain (backend/API/auth hosts), not just the
        # entered URL's domain. Static assets and tracking are still removed.
        entries = filter_traffic(entries)

    output = args.output or "traffic.json"
    with open(output, "w", encoding="utf-8") as file:
        json.dump(entries, file, indent=2)
    print(f"Captured {len(entries)} requests -> {output}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a connector definition against the connector-spec schema."""
    from validate import validate_connector

    with open(args.connector, "r", encoding="utf-8") as file:
        connector = json.load(file)
    is_valid, error = validate_connector(connector)
    if not is_valid:
        print(f"INVALID: {error}")
        return 1
    print("VALID")
    return 0


def cmd_model(args: argparse.Namespace) -> int:
    """Show or set the default LLM provider/model, and manage aliases."""
    from cli import config

    if args.set:
        model_spec = args.set
        config.set_model(model_spec)
        print(f"Default model set to: {model_spec}")
        return 0

    if args.provider:
        config.set_provider(args.provider)
        print(f"Default provider set to: {args.provider}")
        return 0

    if args.show_aliases:
        aliases = config.get_aliases()
        if not aliases:
            print("No user aliases defined.")
        for name, value in aliases.items():
            print(f"{name} = {value}")
        return 0

    if args.alias:
        name, _, value = args.alias.partition("=")
        config.set_alias(name.strip(), value.strip())
        print(f"Alias '{name.strip()}' -> {value.strip()}")
        return 0

    # Show current config
    model = config.get_model()
    provider = config.get_provider()
    print(f"Model:    {model or '(not set)'}")
    print(f"Provider: {provider or '(not set)'}")
    print("Set one with `web2actions model <provider>/<model>`.")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Serve a connector definition as an MCP server over stdio."""
    import asyncio
    from serve import run_stdio

    with open(args.connector, "r", encoding="utf-8") as file:
        connector = json.load(file)

    auth_provider = None
    if args.auth:
        from auth import auth_provider_from_file
        auth_provider = auth_provider_from_file(args.auth)

    asyncio.run(run_stdio(connector, auth_provider=auth_provider))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="web2actions", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_model = sub.add_parser("model", help="Show or set the default LLM provider/model, manage aliases")
    p_model.add_argument("set", nargs="?", help="Set default model, e.g. openai/gpt-4o-mini")
    p_model.add_argument("--provider", help="Set default provider")
    p_model.add_argument("--alias", help="Set an alias, e.g. tom=openai/gpt-4o-mini")
    p_model.add_argument("--aliases", dest="show_aliases", action="store_true", help="List aliases")
    p_model.set_defaults(func=cmd_model)

    p_cap = sub.add_parser("capture", help="Open a browser, record traffic for the user's login + actions")
    p_cap.add_argument("url", help="The website URL to open")
    p_cap.add_argument("--login", action="store_true", help="Automate a form login (needs --username/--password)")
    p_cap.add_argument("--username", help="Username for --login")
    p_cap.add_argument("--password", help="Password for --login")
    p_cap.add_argument("--username-selector", default="#username")
    p_cap.add_argument("--password-selector", default="#password")
    p_cap.add_argument("--submit-selector", default="#submit-btn")
    p_cap.add_argument("--success-indicator", help="Selector to wait for after login")
    p_cap.add_argument("--filter", action="store_true", help="Filter out noise from the captured dump")
    p_cap.add_argument("--output", "-o", help="Output traffic path (default traffic.json)")
    p_cap.add_argument("--auto-pages", type=int, default=6,
                       help="How many common pages to auto-visit after you press Enter (default 6)")
    p_cap.set_defaults(func=cmd_capture)

    p_gen = sub.add_parser("generate", help="Produce a connector definition from a traffic dump")
    p_gen.add_argument("traffic", help="Path to a captured traffic dump (JSON)")
    p_gen.add_argument("--model", help="LLM model name (or set WEB2ACTIONS_MODEL)")
    p_gen.add_argument("--output", "-o", help="Output connector path (default connector.json)")
    p_gen.set_defaults(func=cmd_generate)

    p_val = sub.add_parser("validate", help="Validate a connector definition")
    p_val.add_argument("connector", help="Path to a connector definition (JSON)")
    p_val.set_defaults(func=cmd_validate)

    p_serve = sub.add_parser("serve", help="Serve a connector definition as an MCP server")
    p_serve.add_argument("connector", help="Path to a connector definition (JSON)")
    p_serve.add_argument("--auth", help="Path to an auth JSON file (token and/or cookies) to authenticate tool calls")
    p_serve.set_defaults(func=cmd_serve)

    # Register the agent 'analyze' subcommand (lazy import to avoid cycle).
    try:
        from cli import agent as agent_cli
        agent_cli.add_subparser(sub)
    except Exception as exc:  # noqa: BLE001
        print(f"warning: analyze subcommand unavailable ({exc})", file=sys.stderr)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())