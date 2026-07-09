"""Pattern sets for the evidence gate.

Three families of patterns:

* **Claim** patterns  — phrases that assert a task is finished.
* **Evidence** patterns — concrete, checkable signals (command output, file
  paths, URLs, measured results, explicit "evidence:" notes).
* **Hedge** patterns   — honest uncertainty markers. A line that hedges is
  never treated as an unsupported claim.

Everything here is a heuristic, on purpose. The gate is a linter, not a proof
system: it nudges writers to put evidence next to claims. Tune the word sets to
your team's style with ``--strict`` (broader) or ``--prose`` (more conservative).
"""
from __future__ import annotations

import re

# --- Claim patterns -------------------------------------------------------

# "done" with completion-claim context — not every English use of the word.
# Catches agent/status phrasing ("All done.", "done!", "is done", list items)
# while skipping narrative like "when she was done cooking" or "well done".
_DONE_CLAIM = (
    r"(?:"
    r"\b(?:all|mostly|finally)\s+done\b"
    r"|\b(?:is|are|we're|we\s+are|it's|it\s+is|now)\s+done\b"
    r"|(?<![\w'])done(?=\s*(?:[.!…]|$|[—–\-:)]))"
    r"|(?:^|[\-\*]\s+|:\s*)done\b"
    r")"
)

# Default set: high-precision completion assertions. These read as "this is
# finished" far more often than they appear in neutral prose.
_DEFAULT_CLAIMS = [
    ("done", _DONE_CLAIM),
    ("checkmark", r"✅"),
    ("tests_pass", r"\b(?:all\s+)?tests?\s+(?:pass|passed|passing|green)\b"),
    ("ready_to", r"\bready\s+to\s+(?:ship|merge|deploy|release|go)\b"),
    ("completed", r"\bcomplet(?:ed|ely)\b"),
    ("verified", r"\bverif(?:y|ied|ies)\b"),
    ("confirmed", r"\bconfirm(?:ed|s)?\b"),
    ("fixed", r"\bfix(?:ed|es)\b"),
    ("shipped", r"\bshipp(?:ed)?\b"),
    ("successfully", r"\bsuccessfully\s+\w+"),
    # Prefer "works now" / "is now working" over bare "working".
    ("now_working", r"\b(?:is\s+)?now\s+working\b|\bworks?\s+now\b|\bis\s+working\b"),
]

# Prose mode: still stricter — tuned for narrative / long-form text where
# words like "fixed", "completed", "working" appear without being status claims.
_PROSE_CLAIMS = [
    ("done", _DONE_CLAIM),
    ("checkmark", r"✅"),
    ("tests_pass", r"\b(?:all\s+)?tests?\s+(?:pass|passed|passing|green)\b"),
    ("ready_to", r"\bready\s+to\s+(?:ship|merge|deploy|release|go)\b"),
    # Prefer "completed" as a status verb, not "completely".
    ("completed", r"\bcompleted\b"),
    ("verified", r"\bverif(?:ied|ies)\b"),  # drop bare "verify" (imperative)
    ("confirmed", r"\bconfirmed\b"),
    # "fixed the bug" / "bug is fixed" / "is fixed." — not "fixed income".
    (
        "fixed",
        r"\b(?:fix(?:ed|es)\s+(?:the|a|an|our|my|this|that|it)\b|"
        r"(?:is|are|was|were|been)\s+fixed\b|"
        r"\bfixed\s*[.!]|\bfixed\s*[—–\-:])",
    ),
    ("shipped", r"\bshipped\b"),
    ("successfully", r"\bsuccessfully\s+(?:completed|deployed|shipped|fixed|migrated|released)\b"),
    ("now_working", r"\bworks?\s+now\b|\bis\s+now\s+working\b"),
]

# Strict set: broader, noisier words. Opt in with ``--strict``.
_STRICT_EXTRA = [
    ("pass", r"\bpass(?:es|ed)\b"),
    ("complete", r"\bcomplete\b"),
    ("deploy", r"\bdeploy(?:ed|s)?\b"),
    ("resolved", r"\bresolv(?:e|ed|es)\b"),
    ("success", r"\bsuccess(?:ful|fully)?\b"),
    ("green", r"\bgreen\b"),
    ("hundred_pct", r"\b100\s*%\b"),
    ("good_to_go", r"\bgood\s+to\s+go\b"),
    ("no_issues", r"\bno\s+(?:issues|errors|problems|bugs)\b"),
    # Loose "done" for teams that want every occurrence scanned.
    ("done_loose", r"\bdone\b"),
]


def claim_regexes(strict: bool = False, prose: bool = False):
    """Return a list of ``(name, compiled_regex)`` claim patterns.

    Parameters
    ----------
    strict:
        Include the broader (noisier) claim word set.
    prose:
        Use the conservative prose-oriented claim set (fewer false positives
        on narrative text). Compatible with ``strict`` extras.
    """
    items = list(_PROSE_CLAIMS if prose else _DEFAULT_CLAIMS)
    if strict:
        items = items + list(_STRICT_EXTRA)
    return [(name, re.compile(pat, re.IGNORECASE)) for name, pat in items]


# --- Evidence patterns ----------------------------------------------------

_EVIDENCE = [
    r"^\s*```",                                              # fenced code block
    r"^\s*[$>]\s+\S",                                        # shell prompt line
    r"https?://\S+",                                         # URL
    r"`[^`]{2,}`",                                           # inline code span
    r"(?:[\w.\-]+[\\/])+[\w.\-]+",                           # path with a separator
    (
        r"\b[\w\-]+\.(?:py|js|ts|tsx|jsx|md|json|jsonl|txt|ya?ml|toml|"
        r"sh|ps1|go|rs|java|c|cpp|h|hpp|html|css|cff|lock|cfg|ini|sql|"
        r"csv|rb|php|kt|swift|scala|lua)\b"                  # filename.ext
    ),
    r"\b\d+\s+(?:passed|passing|failed|failing|tests?|cases?|files?|rows?|"
    r"errors?|warnings?|vulnerabilities|assertions?)\b",     # "12 passed", "0 errors"
    r"\b(?:exit(?:\s*code)?|status|returned)\s*[:=]?\s*0\b",  # exit code 0
    r"\b0\s+(?:errors?|failures?|vulnerabilities|warnings?)\b",
    r"\b\d+(?:\.\d+)?\s*(?:ms|sec|s|%|MB|GB|KB|bytes?|tokens?|req/s)\b",  # measurement
    r"(?:evidence|output|result|readback|proof|verified\s+by|logs?|"
    r"screenshot|see)\s*[:=]",                               # explicit lead-in
]
EVIDENCE_REGEXES = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in _EVIDENCE]


# --- Hedge patterns -------------------------------------------------------

_HEDGES = [
    r"\bUNKNOWN\b",
    r"\bUNVERIFIED\b",
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\bWIP\b",
    r"\bdraft\b",
    r"\bnot\s+(?:yet\s+)?(?:tested|verified|done|working|implemented|sure)\b",
    r"\bassum(?:e|es|ed|ption|ing)\b",
    r"\bI\s+think\b",
    r"\bprobably\b",
    r"\bshould\b",
    r"\bmight\b",
    r"\bappears?\s+to\b",
    r"\bneeds?\s+(?:review|verification|testing)\b",
]
HEDGE_REGEXES = [re.compile(p, re.IGNORECASE) for p in _HEDGES]
