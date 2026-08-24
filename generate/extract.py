"""
Traffic-to-connector extraction for Web2Actions (Generate, cheap path).

Takes a filtered traffic dump, asks an LLM to produce a connector-definition
JSON, validates it against the module 1 connector-spec schema, and returns
the validated connector definition.

The LLM provider is provider-agnostic via the `anyllm` library: the caller
passes a model name (e.g. "gpt-4o", "claude-sonnet-4", "deepseek-chat") and
anyllm resolves the provider at runtime, so it can be switched without code
changes.
"""

import json
import os
import sys
from typing import Any, Dict, List

import anyllm

# Resolve the generate package sibling status module.
from status import ExtractionStatus  # noqa: E402

# Resolve the sibling connector-spec package so we can reuse its validator.
_SIBLING = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "connector-spec"))
if _SIBLING not in sys.path:
    sys.path.insert(0, _SIBLING)

from validate import validate_connector  # noqa: E402

# Path to the extraction prompt template.
_PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")
_EXTRACTION_PROMPT_PATH = os.path.join(_PROMPT_DIR, "extraction.txt")


def load_extraction_prompt() -> str:
    """Load the extraction prompt template from the prompts folder."""
    with open(_EXTRACTION_PROMPT_PATH, "r", encoding="utf-8") as file:
        return file.read()


def build_extraction_prompt(traffic_dump: List[Dict[str, Any]]) -> str:
    """Fill the extraction prompt template with the traffic dump."""
    template = load_extraction_prompt()
    return template.format(traffic_dump=json.dumps(traffic_dump, indent=2))


def run_llm_extraction(
    traffic_dump: List[Dict[str, Any]],
    model: str,
) -> dict:
    """
    Call the LLM (provider resolved from the model name by anyllm) to derive a
    connector definition, and parse the JSON response.
    """
    prompt = build_extraction_prompt(traffic_dump)
    response = anyllm.chat(prompt, model=model)
    parsed = json.loads(str(response))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response was not a JSON object")
    return parsed


def extract_connector_definition(
    traffic_dump: List[Dict[str, Any]],
    model: str,
) -> dict:
    """
    Run LLM extraction and validate the result against the connector schema.
    Returns the validated connector definition, or raises if it is invalid.
    """
    candidate = run_llm_extraction(traffic_dump, model)
    is_valid, error_message = validate_connector(candidate)
    if not is_valid:
        raise ValueError(f"Extracted connector failed schema validation: {error_message}")
    return candidate


def run_extraction_job(
    traffic_dump: List[Dict[str, Any]],
    model: str,
) -> Dict[str, Any]:
    """
    Run one extraction job and return a status-flagged result, never raising.

    On success: {"status": "success", "connector": {...}}.
    On invalid/parseable-but-wrong output: {"status": "needs_escalation",
    "errors": [...]}. The job is never silently marked done when the cheap path
    fails — it is flagged for the sandboxed fallback (module 6) instead.
    """
    try:
        candidate = run_llm_extraction(traffic_dump, model)
        is_valid, error_message = validate_connector(candidate)
        if not is_valid:
            return {
                "status": ExtractionStatus.NEEDS_ESCALATION.value,
                "connector": candidate,
                "errors": [error_message],
            }
        return {"status": ExtractionStatus.SUCCESS.value, "connector": candidate}
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "status": ExtractionStatus.NEEDS_ESCALATION.value,
            "connector": None,
            "errors": [str(exc)],
        }