"""
Interactive clarifying questions for the Web2Actions agent (Module 17 / STORY-17.4).

When the agent analyzes captured traffic it often needs a few clarifications —
what a confusing endpoint is for, which calls are write vs. read, how to group
resources, etc. This module presents those as numbered menus with suggested
options (like Claude Code), and supports a `--assume` mode that picks the
recommended default automatically for fully-automated runs.
"""

from typing import Any, Dict, List, Optional


class AskResult:
    """The user's answers to a set of clarifying questions."""

    def __init__(self) -> None:
        self.answers: Dict[str, Any] = {}
        self.assumed: List[str] = []  # question keys answered via --assume

    def get(self, key: str, default: Any = None) -> Any:
        return self.answers.get(key, default)


def suggested_questions(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build a small set of clarifying questions from the captured traffic, each
    with numbered options and a recommended default.

    Returns a list of dicts:
        {"key", "prompt", "options": [(label, value)...], "default": value}
    """
    # Determine whether the traffic shows an obvious login/auth call.
    has_auth = any(
        (e.get("method", "").upper() in ("POST", "PUT")
         and any(t in (e.get("url", "")).lower() for t in ("/login", "/auth", "/signin", "/token")))
        for e in entries
    )

    has_write = any(e.get("method", "").upper() in ("POST", "PUT", "PATCH", "DELETE") for e in entries)

    questions: List[Dict[str, Any]] = []

    if has_auth:
        questions.append({
            "key": "auth",
            "prompt": "How should the connector handle authentication?",
            "options": [
                ("Reuse the logged-in session cookies (recommended)", "session"),
                ("Treat login as a tool", "login_tool"),
                ("No auth (public endpoints)", "none"),
            ],
            "default": "session",
        })

    if has_write:
        questions.append({
            "key": "write_handling",
            "prompt": "How should write operations (create/update/delete) be exposed?",
            "options": [
                ("As separate named tools (recommended)", "separate"),
                ("Grouped under one generic mutator", "generic"),
            ],
            "default": "separate",
        })

    questions.append({
        "key": "risk_confirmation",
        "prompt": "Confirm risk tagging for the discovered tools?",
        "options": [
            ("Auto-tag by HTTP method (recommended)", "auto"),
            ("Review each tool manually", "manual"),
        ],
        "default": "auto",
    })

    return questions


def ask(
    questions: List[Dict[str, Any]],
    assume: bool = False,
    input_fn: Optional[Any] = None,
) -> AskResult:
    """
    Ask the user the given questions (numbered menus) or apply defaults.

    When `assume` is True, no prompt is shown — every question uses its
    recommended default. `input_fn` is injectable for tests; defaults to
    builtins.input.
    """
    result = AskResult()
    if input_fn is None:
        import builtins
        input_fn = builtins.input

    for q in questions:
        key = q["key"]
        if assume:
            result.answers[key] = q["default"]
            result.assumed.append(key)
            continue

        print(f"\n{q['prompt']}")
        for i, (label, _value) in enumerate(q["options"], start=1):
            marker = " (recommended)" if q["default"] == _value else ""
            print(f"  {i}. {label}{marker}")
        choice = input_fn("Choose [1]: ").strip()
        if not choice:
            result.answers[key] = q["default"]
        else:
            try:
                idx = int(choice)
                result.answers[key] = q["options"][idx - 1][1]
            except (ValueError, IndexError):
                result.answers[key] = q["default"]
    return result