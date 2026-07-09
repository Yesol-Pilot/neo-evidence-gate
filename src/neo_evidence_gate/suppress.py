"""Inline and file-based suppressions for known accepted claims.

Two mechanisms:

1. **Inline** — put ``# noqa: evidence-gate`` on the claim line (same spirit
   as flake8/ruff noqa). That single line is skipped.
2. **Ignore file** — a small text file of ``path:line`` entries or path
   globs so documented exceptions live next to the project, not in the
   source under review.
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable, Optional, Set

# Accept common comment styles so the pragma works in md/py/js-ish text.
# Examples:
#   All done.  # noqa: evidence-gate
#   All done.  // noqa: evidence-gate
#   All done.  <!-- noqa: evidence-gate -->
NOQA_RE = re.compile(
    r"(?:#|//|/\*+|<!--)\s*noqa\s*:\s*evidence-gate\b",
    re.IGNORECASE,
)


def line_suppressed(line: str) -> bool:
    """Return True if ``line`` carries an evidence-gate noqa pragma."""
    return bool(NOQA_RE.search(line))


@dataclass
class IgnoreRules:
    """Parsed ignore-file rules.

    * ``whole_files`` — path patterns (fnmatch) that suppress every line.
    * ``lines`` — map of path pattern -> set of 1-indexed line numbers.
    """

    whole_files: Set[str] = field(default_factory=set)
    lines: dict = field(default_factory=dict)  # pattern -> set[int]
    source: Optional[str] = None

    def suppresses(self, path: str, line_no: int) -> bool:
        """Return True if ``path`` at ``line_no`` (1-indexed) is ignored."""
        if not self.whole_files and not self.lines:
            return False
        candidates = _path_candidates(path)
        for pattern in self.whole_files:
            if any(fnmatch.fnmatch(c, pattern) for c in candidates):
                return True
        for pattern, linenos in self.lines.items():
            if line_no in linenos and any(
                fnmatch.fnmatch(c, pattern) for c in candidates
            ):
                return True
        return False

    @property
    def empty(self) -> bool:
        return not self.whole_files and not self.lines


def _path_candidates(path: str) -> Set[str]:
    """Normalizations used when matching ignore patterns."""
    if path in ("-", "stdin"):
        return {"stdin", "-"}
    p = path.replace("\\", "/")
    name = PurePosixPath(p).name
    out = {p, name}
    # Also try without a leading ./
    if p.startswith("./"):
        out.add(p[2:])
    return out


def parse_ignore_text(text: str, *, source: Optional[str] = None) -> IgnoreRules:
    """Parse ignore-file contents into :class:`IgnoreRules`.

    Format (one entry per line, ``#`` comments and blanks ignored)::

        # ignore an entire path or glob
        docs/legacy.md
        reports/**/old-*.md

        # ignore a specific line
        examples/bad.md:3
        path/with spaces.md:12
    """
    rules = IgnoreRules(source=source)
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Split on the last ":digits" so Windows drive letters stay intact
        # only when the suffix is a pure line number.
        path_part, line_no = _split_path_line(line)
        path_part = path_part.replace("\\", "/").strip()
        if not path_part:
            continue
        if line_no is None:
            rules.whole_files.add(path_part)
        else:
            rules.lines.setdefault(path_part, set()).add(line_no)
    return rules


def _split_path_line(entry: str):
    """Split ``path:line`` into ``(path, line_or_None)``.

    Only treats a trailing ``:N`` where N is a positive integer as a line
    marker, so ``C:/foo/bar.md`` is not misparsed on Windows-style paths.
    """
    if ":" not in entry:
        return entry, None
    # Walk from the right: require the suffix after the last colon to be digits.
    head, _, tail = entry.rpartition(":")
    if head and tail.isdigit() and int(tail) > 0:
        # Avoid treating "C:" as path with line on bare drive-ish inputs.
        # "C:3" is weird; "file.md:3" is fine; "C:/x.md:3" is fine.
        if len(head) == 1 and head.isalpha():
            return entry, None
        return head, int(tail)
    return entry, None


def load_ignore_file(path: str) -> IgnoreRules:
    """Load an ignore file from disk."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    return parse_ignore_text(text, source=str(p))


def discover_ignore_file(start: Optional[Path] = None) -> Optional[Path]:
    """Walk parents for ``.neo-evidence-gate-ignore``."""
    cur = (start or Path.cwd()).resolve()
    if cur.is_file():
        cur = cur.parent
    for directory in [cur, *cur.parents]:
        candidate = directory / ".neo-evidence-gate-ignore"
        if candidate.is_file():
            return candidate
        if directory.parent == directory:
            break
    return None


def load_ignore(
    path: Optional[str] = None,
    *,
    start: Optional[Path] = None,
    discover: bool = True,
) -> IgnoreRules:
    """Load ignore rules from ``path`` or discover ``.neo-evidence-gate-ignore``."""
    if path:
        return load_ignore_file(path)
    if not discover:
        return IgnoreRules()
    found = discover_ignore_file(start)
    if not found:
        return IgnoreRules()
    return load_ignore_file(str(found))
