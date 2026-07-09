"""Core gate: find completion claims that lack nearby evidence.

The rule is deliberately simple and teachable:

    A completion claim ("done", "tests pass", "verified", ...) must be
    accompanied by concrete evidence on the same line or within a short
    window *after* it. Otherwise it is flagged.

Evidence before a later claim is not counted by default (``back=0``), because
it usually belongs to an earlier claim — the discipline the gate teaches is
"state the claim, then show the proof". Teams whose logs put output first can
pass ``back=N``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union

from .config import GateConfig
from .rules import claim_regexes, evidence_regexes, hedge_regexes


@dataclass
class Finding:
    """A single unsupported completion claim."""

    line: int          # 1-indexed line number
    text: str          # the offending line, stripped
    claim: str         # the matched claim phrase
    reason: str = "completion claim without nearby evidence"

    def as_dict(self) -> dict:
        return {
            "line": self.line,
            "text": self.text,
            "claim": self.claim,
            "reason": self.reason,
        }


@dataclass
class GateResult:
    findings: List[Finding] = field(default_factory=list)
    claims_total: int = 0
    lines_scanned: int = 0

    @property
    def ok(self) -> bool:
        return not self.findings


def _window(lines: List[str], i: int, back: int, fwd: int) -> str:
    lo = max(0, i - back)
    hi = min(len(lines), i + fwd + 1)
    return "\n".join(lines[lo:hi])


def check_text(
    text: str,
    *,
    strict: bool = False,
    window: int = 4,
    back: int = 0,
    config: Optional[Union[GateConfig, None]] = None,
) -> GateResult:
    """Scan ``text`` and return a :class:`GateResult`.

    Parameters
    ----------
    strict:
        Include the broader (noisier) claim word set.
    window:
        Number of lines *after* a claim to search for evidence.
    back:
        Number of lines *before* a claim to search for evidence (default 0).
    config:
        Optional :class:`GateConfig` with project-specific pattern
        extensions or replacements. When omitted, built-in defaults are used.
    """
    lines = text.splitlines()
    cfg = config or GateConfig()

    claims = claim_regexes(
        strict=strict,
        extra=cfg.claims_add or None,
        replace=cfg.claims_replace,
    )
    evidence = evidence_regexes(
        extra=cfg.evidence_add or None,
        replace=cfg.evidence_replace,
    )
    hedges = hedge_regexes(
        extra=cfg.hedges_add or None,
        replace=cfg.hedges_replace,
    )
    result = GateResult(lines_scanned=len(lines))

    for i, line in enumerate(lines):
        # An honestly-hedged line is never an unsupported claim.
        if any(h.search(line) for h in hedges):
            continue

        matched = None
        for _name, rx in claims:
            m = rx.search(line)
            if m:
                matched = m.group(0).strip()
                break
        if not matched:
            continue

        result.claims_total += 1
        win = _window(lines, i, back, window)
        if any(rx.search(win) for rx in evidence):
            continue

        result.findings.append(
            Finding(line=i + 1, text=line.strip(), claim=matched)
        )

    return result
