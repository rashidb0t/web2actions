"""
`web2actions analyze` — run the agent harness over captured traffic.

Wraps the vendored CLI-Anything-Web harness with the provider-agnostic LLM
backend (`agent/llm.py`), so the same discovery logic works on any provider,
not just Claude.
"""

import argparse
import os
import sys
from typing import Optional


def _add_paths() -> None:
    """Ensure the repo root (and thus the `agent` and `cli` packages) importable.

    Adds the repo root, not the package directories, so 'agent' resolves as a
    real package from any invocation.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    harness = os.path.join(root, "agent", "harness")
    if harness not in sys.path:
        sys.path.insert(0, harness)


def cmd_analyze(args: argparse.Namespace) -> int:
    """Analyze a captured traffic dump and report the discovered API surface."""
    _add_paths()

    if not args.dump:
        print("Missing traffic dump. Usage: web2actions analyze <traffic.json>")
        return 1

    try:
        with open(args.dump, "r", encoding="utf-8") as f:
            import json
            entries = json.load(f)
    except Exception as exc:  # noqa: BLE001
        print(f"Could not read traffic dump: {exc}")
        return 1

    if not isinstance(entries, list) or not entries:
        print("Traffic dump is empty or not a JSON array.")
        return 1

    from agent import llm as llm_backend
    from agent.llm import resolve_model

    model = resolve_model(args.model)
    print(f"Analyzing {len(entries)} requests with model: {model}")

    # Summarize domains and methods so the LLM (and user) see the surface.
    from urllib.parse import urlparse
    from collections import Counter
    domains = Counter(urlparse(e.get("url", "")).netloc for e in entries)
    methods = Counter(e.get("method", "GET") for e in entries)
    print(f"Domains: {dict(domains)}")
    print(f"Methods: {dict(methods)}")

    summary = "\n".join(
        f"[{e.get('method','GET')}] {e.get('url','')}" for e in entries[:150]
    )
    prompt = (
        "You are reverse-engineering the API of a web app from captured traffic.\n"
        "List the meaningful API endpoints (not static assets), each with:\n"
        "- method, full URL\n"
        "- a short human name (verb + resource)\n"
        "- a one-line purpose\n"
        "Ignore charts, fonts, _rsc/HTML server-rendering routes, and tracking.\n\n"
        f"CAPTURED TRAFFIC:\n{summary}"
    )
    system = (
        "You are an API discovery agent. Output a concise numbered list of real "
        "endpoints with name, risk (read/write/destructive), and purpose."
    )
    try:
        report = llm_backend.chat(prompt, model, system=system)
    except Exception as exc:  # noqa: BLE001
        print(f"LLM analysis failed: {exc}")
        print("Ensure the provider key is set (e.g. GEMINI_API_KEY) and a model is configured.")
        return 1

    print("\n=== Discovered API surface ===")
    print(report)
    return 0


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the analyze subcommand on the CLI parser."""
    p = subparsers.add_parser(
        "analyze", help="Analyze captured traffic and discover the API surface (agent harness)"
    )
    p.add_argument("dump", nargs="?", help="Path to a captured traffic JSON dump")
    p.add_argument("--model", help="LLM model (or use saved config / WEB2ACTIONS_MODEL)")
    p.set_defaults(func=cmd_analyze)