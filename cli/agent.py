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

    # Refuse if the dump contains challenge signals.
    from agent.guards import CHALLENGE_MESSAGE, detect_challenges
    verdict = detect_challenges(entries)
    if verdict["blocked"]:
        print(CHALLENGE_MESSAGE.format(reasons=", ".join(verdict["reasons"])))
        return 1

    from agent import llm as llm_backend
    from agent.llm import resolve_model
    from agent.questions import ask, suggested_questions

    model = resolve_model(args.model)
    print(f"Analyzing {len(entries)} requests with model: {model}")

    # Ask clarifying questions (or use defaults with --assume).
    qs = suggested_questions(entries)
    if qs:
        answers = ask(qs, assume=args.assume)
        print(f"  (assumed: {', '.join(answers.assumed) or 'none'})")

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
        "You are reverse-engineering a web app from captured traffic into tool definitions.\n"
        "The user logged in and visited several pages. Each distinct page/route they visited\n"
        "is a real resource and should become a tool that loads that page's data.\n"
        "List them, each with:\n"
        "- method, full URL\n"
        "- a short human name (verb + resource), e.g. 'list_tasks' for the tasks page\n"
        "- a one-line purpose\n"
        "- risk (read/write/destructive)\n"
        "Ignore only true noise: charts/fonts/images, static asset bundles (.js/.css/.woff), "
        "and tracking. Do NOT drop page routes like /dashboard, /tasks, /projects, /kanban, "
        "/backlog — keep each as a tool.\n\n"
        f"CAPTURED TRAFFIC:\n{summary}"
    )
    system = (
        "You are an API discovery agent. Output a concise numbered list of real "
        "endpoints/page-routes with name, method, risk (read/write/destructive), and purpose. "
        "Every page the user visited is a tool — do not omit them."
    )
    try:
        report = llm_backend.chat(prompt, model, system=system)
    except Exception as exc:  # noqa: BLE001
        print(f"LLM analysis failed: {exc}")
        print("Ensure the provider key is set (e.g. GEMINI_API_KEY) and a model is configured.")
        return 1

    print("\n=== Discovered API surface ===")
    print(report)

    # Optionally turn the discovered endpoints into a connector definition JSON.
    if args.output:
        from agent.to_connector import build_connector, parse_report
        from urllib.parse import urlparse

        endpoints = parse_report(report)
        if not endpoints:
            print("No endpoints parsed from the report; nothing to write.")
            return 1
        host = urlparse(args.url or "https://example.com").netloc.replace(".", "-")
        connector = build_connector(
            endpoints, name=host or "connector", website_url=args.url or "https://example.com"
        )
        import json

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(connector, f, indent=2)
        print(f"Wrote connector ({len(connector['tools'])} tools) -> {args.output}")
    return 0


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the analyze subcommand on the CLI parser."""
    p = subparsers.add_parser(
        "analyze", help="Analyze captured traffic and discover the API surface (agent harness)"
    )
    p.add_argument("dump", nargs="?", help="Path to a captured traffic JSON dump")
    p.add_argument("--model", help="LLM model (or use saved config / WEB2ACTIONS_MODEL)")
    p.add_argument("--url", help="The site URL (used as the connector websiteUrl / name)")
    p.add_argument("--output", "-o", help="Write the discovered connector definition JSON to this path")
    p.add_argument("--assume", action="store_true",
                   help="Answer clarifying questions with recommended defaults (no prompt)")
    p.set_defaults(func=cmd_analyze)