"""neo-evidence-gate: an honesty linter that flags completion claims
(DONE / PASS / READY / VERIFIED ...) which lack backing evidence.

Public API:

    >>> from neo_evidence_gate import check_text
    >>> check_text("All done. Everything works.").ok
    False
    >>> check_text("Fixed it.\\n$ pytest\\n12 passed").ok
    True
"""
from .gate import check_text, GateResult, Finding
from .suppress import IgnoreRules, load_ignore, line_suppressed

__all__ = [
    "check_text",
    "GateResult",
    "Finding",
    "IgnoreRules",
    "load_ignore",
    "line_suppressed",
    "__version__",
]
__version__ = "0.1.0"
