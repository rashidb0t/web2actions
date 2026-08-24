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
    """Return the model name, from --model or WEB2ACTIONS_MODEL env, defaulting to a safe choice."""
    return model or os.environ.get("WEB2ACTIONS_MODEL", "gpt-4o-mini")


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


def cmd_serve(args: argparse.Namespace) -> int:
    """Serve a connector definition as an MCP server over stdio."""
    import asyncio
    from serve import run_stdio

    with open(args.connector, "r", encoding="utf-8") as file:
        connector = json.load(file)
    asyncio.run(run_stdio(connector))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="web2actions", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

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
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())