"""
Sandboxed escalation runner for Web2Actions (Generate, module 6).

When the cheap-path extraction fails validation, this escalates to a stronger
model to iterate on the connector-definition JSON until it passes the module 1
schema. It fixes only the JSON connector definition, never builds an
application. The runner is designed to execute inside an isolated sandbox
(no host filesystem access; network egress limited to the target site and the
LLM API) — the sandbox boundary itself is a deployment concern.
"""

import json
import os
from typing import Any, Dict, List, Tuple

from status import ExtractionStatus


# Resolve the sibling connector-spec package for validation.
import sys
_SIBLING = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "connector-spec"))
if _SIBLING not in sys.path:
    sys.path.insert(0, _SIBLING)

from validate import validate_connector  # noqa: E402

_PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")
_ESCALATION_PROMPT_PATH = os.path.join(_PROMPT_DIR, "escalation.txt")


def load_escalation_prompt() -> str:
    """Load the escalation prompt template from the prompts folder."""
    with open(_ESCALATION_PROMPT_PATH, "r", encoding="utf-8") as file:
        return file.read()


def build_escalation_prompt(
    traffic_dump: List[Dict[str, Any]],
    previous_connector: Dict[str, Any],
    validation_errors: List[str],
) -> str:
    """Fill the escalation prompt template with the failure context."""
    template = load_escalation_prompt()
    return template.format(
        traffic_dump=json.dumps(traffic_dump, indent=2),
        previous_connector=json.dumps(previous_connector, indent=2),
        validation_errors=json.dumps(validation_errors, indent=2),
    )


def _validate_connector_candidate(candidate: Dict[str, Any]) -> Tuple[bool, str]:
    """Return (is_valid, error_message) for a connector candidate."""
    return validate_connector(candidate)


def escalate_and_repair(
    traffic_dump: List[Dict[str, Any]],
    previous_connector: Dict[str, Any],
    validation_errors: List[str],
    llm_call,
    max_attempts: int = 3,
) -> Dict[str, Any]:
    """
    Ask a stronger-model LLM to repair the connector, validating the result.
    Repeats up to max_attempts. Returns a status-flagged result:
    {"status": "success", "connector": ...} or
    {"status": "needs_escalation", "errors": [...]} if it never passes.
    """
    errors_so_far = list(validation_errors)
    attempts = 0

    while attempts < max_attempts:
        attempts += 1
        prompt = build_escalation_prompt(traffic_dump, previous_connector, errors_so_far)
        try:
            raw = llm_call(prompt)
            candidate = json.loads(str(raw))
        except (json.JSONDecodeError, ValueError) as exc:
            errors_so_far.append(f"LLM returned unparseable output on attempt {attempts}: {exc}")
            continue

        if not isinstance(candidate, dict):
            errors_so_far.append(f"LLM returned non-object on attempt {attempts}")
            continue

        is_valid, error_message = _validate_connector_candidate(candidate)
        if is_valid:
            return {"status": ExtractionStatus.SUCCESS.value, "connector": candidate}
        errors_so_far.append(f"Attempt {attempts}: {error_message}")
        previous_connector = candidate

    return {
        "status": ExtractionStatus.NEEDS_ESCALATION.value,
        "connector": previous_connector,
        "errors": errors_so_far,
    }