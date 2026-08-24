"""
Traffic-to-connector extraction for Web2Actions (Generate, cheap path).

Takes a filtered traffic dump, asks an LLM to produce a connector-definition
JSON, validates it against the module 1 connector-spec schema, and returns
the validated connector definition.
"""

import json
import sys
from typing import Any, Callable, Dict, List

# Resolve the sibling connector-spec package so we can reuse its validator.
import os
_SIBLING = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "connector-spec"))
if _SIBLING not in sys.path:
    sys.path.insert(0, _SIBLING)

from validate import validate_connector  # noqa: E402


def build_extraction_prompt(traffic_dump: List[Dict[str, Any]]) -> str:
    """Build the LLM system prompt for extracting a connector definition."""
    return (
        "You are given network traffic captured from a website user's browser "
        "session. Produce a Web2Actions connector definition (JSON) following "
        "the connector specification schema: fields name, version, description, "
        "websiteUrl, auth, tools. Each tool needs a name, description, risk "
        "(read/write/destructive), inputSchema, outputSchema, and call "
        "(method, url, headers, body). Keep names plain and English.\n\n"
        "Traffic dump:\n"
        + json.dumps(traffic_dump, indent=2)
    )


def run_llm_extraction(
    traffic_dump: List[Dict[str, Any]],
    llm_call: Callable[[str], str],
) -> dict:
    """
    Call the LLM to derive a connector definition, parse the JSON response,
    and return it. Uses the caller-provided llm_call function so tests can mock
    the model call (no live API budget needed).
    """
    prompt = build_extraction_prompt(traffic_dump)
    raw = llm_call(prompt)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("LLM response was not a JSON object")
    return parsed


def extract_connector_definition(
    traffic_dump: List[Dict[str, Any]],
    llm_call: Callable[[str], str],
) -> dict:
    """
    Run LLM extraction and validate the result against the connector schema.
    Returns the validated connector definition, or raises if it is invalid.
    """
    candidate = run_llm_extraction(traffic_dump, llm_call)
    is_valid, error_message = validate_connector(candidate)
    if not is_valid:
        raise ValueError(f"Extracted connector failed schema validation: {error_message}")
    return candidate