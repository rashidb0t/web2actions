"""
Extraction outcome status for Web2Actions generate (cheap path).

Distinguishes a successful extraction from one that failed and must be
escalated to the sandboxed fallback (module 6) — never silently marked done.
"""

from enum import Enum


class ExtractionStatus(Enum):
    """The outcome of an extraction attempt."""

    SUCCESS = "success"
    NEEDS_ESCALATION = "needs_escalation"