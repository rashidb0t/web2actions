# Generate Module

This module handles generation of connector definitions from recorded
website traffic. It includes a **cheap path** (single LLM extraction call)
and a **sandboxed fallback** (escalated repair) for more complex cases.

## Cheap path (extraction)

- `prompts/extraction.txt` — the LLM prompt template (loaded by `extract.py` by reference; prompts live in a dedicated folder, not hardcoded).
- `extract.py`
  - `build_extraction_prompt(disp)` / `load_extraction_prompt()` — prompt assembly.
  - `extract_connector_definition(disp, model)` — single extraction + schema validation; raises if invalid.
  - `run_extraction_job(disp, model)` — status-flagged job result (never raises); returns `{status: "success"|"needs_escalation", connector, errors}`.
- `status.py` — `ExtractionStatus` enum (`success` / `needs_escalation`).

The LLM call is provider-agnostic via **`anyllm`**: pass any model name
(e.g. `gpt-4o`, `claude-sonnet-4`, `deepseek-chat`) and the provider is
resolved at runtime — switch providers without code changes.

## Failure detection (STORY-4.2)

If the cheap-path output is invalid (not JSON, or JSON that fails the
module 1 connector-spec validation), `run_extraction_job` returns
`needs_escalation` — the job is **never silently marked done**. The caller
(or module 6's sandboxed fallback) uses that flag to escalate.

## Sandboxed escalation (STORY-6.1)

- `prompts/escalation.txt` — the escalation prompt template.
- `escalate.py`
  - `load_escalation_prompt()` / `build_escalation_prompt(disp, prev, errors)` — prompt assembly.
  - `escalate_and_repair(disp, prev, errors, llm_call, max_attempts)` — asks a
    stronger-model LLM to repair the connector definition, validates the
    result, and repeats up to `max_attempts`. Returns a status-flagged result.
  - Fixes only the JSON connector definition, never an application.
- Designed to run inside an isolated sandbox (no host filesystem access;
  network egress limited to target site + LLM API); the sandbox boundary is a
  deployment concern.

## Tests

- `tests/test_extract.py` — prompt loading, valid extraction, schema/parse failures.
- `tests/test_failure_detection.py` — invalid-JSON and schema-invalid both → `needs_escalation`; valid → `success`.

Run with: `.venv/bin/python -m unittest generate.tests.test_extract generate.tests.test_failure_detection`