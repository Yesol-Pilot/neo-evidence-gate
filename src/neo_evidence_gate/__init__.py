"""neo-evidence-gate: an honesty linter that flags completion claims
(DONE / PASS / READY / VERIFIED ...) which lack backing evidence.

Public API:

    >>> from neo_evidence_gate import check_text
    >>> check_text("All done. Everything works.").ok
    False
    >>> check_text("Fixed it.\\n$ pytest\\n12 passed").ok
    True
"""
from .config import GateConfig, load_config
from .gate import check_text, GateResult, Finding

__all__ = [
    "check_text",
    "GateResult",
    "Finding",
    "GateConfig",
    "load_config",
    "__version__",
]
__version__ = "0.1.0"
