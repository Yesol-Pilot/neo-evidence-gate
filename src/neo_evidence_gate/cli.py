"""Command-line interface for neo-evidence-gate."""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import __version__
from .gate import check_text


def _make_output_utf8_safe() -> None:
    """Avoid UnicodeEncodeError on legacy consoles (e.g. Windows cp949/cp1252).

    Output may contain characters the console codepage can't encode. Reconfigure
    the streams to UTF-8 with a safe fallback so the tool never crashes on the
    text it is asked to lint.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError):  # not a reconfigurable TextIO
            pass


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="neo-evidence-gate",
        description=(
            "Flag completion claims (DONE/PASS/READY/VERIFIED...) that lack "
            "nearby evidence. Reads files or stdin; exits non-zero when "
            "unsupported claims exceed --max."
        ),
    )
    p.add_argument(
        "files",
        nargs="*",
        help="files to check; use '-' or pass nothing to read stdin",
    )
    p.add_argument("--strict", action="store_true",
                   help="use the broader (noisier) claim word set")
    p.add_argument(
        "--prose",
        action="store_true",
        help=(
            "use a more conservative claim set for narrative / long-form "
            "text (fewer false positives on ordinary 'done' / 'fixed')"
        ),
    )
    p.add_argument("--window", type=int, default=4,
                   help="lines after a claim to search for evidence (default 4)")
    p.add_argument("--back", type=int, default=0,
                   help="lines before a claim to search for evidence (default 0)")
    p.add_argument("--json", action="store_true",
                   help="emit findings as JSON")
    p.add_argument("--max", type=int, default=0, metavar="N",
                   help="allowed findings before a non-zero exit (default 0)")
    p.add_argument("--version", action="version",
                   version=f"neo-evidence-gate {__version__}")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    _make_output_utf8_safe()
    args = build_parser().parse_args(argv)
    files = args.files or ["-"]

    all_findings = []
    for path in files:
        try:
            text = _read(path)
        except OSError as exc:
            print(f"error: cannot read {path}: {exc}", file=sys.stderr)
            return 2
        res = check_text(
            text,
            strict=args.strict,
            prose=args.prose,
            window=args.window,
            back=args.back,
        )
        label = "stdin" if path == "-" else path
        for f in res.findings:
            all_findings.append({"file": label, **f.as_dict()})

    if args.json:
        print(json.dumps(
            {"findings": all_findings, "total": len(all_findings)},
            ensure_ascii=False, indent=2,
        ))
    else:
        for f in all_findings:
            print(f"{f['file']}:{f['line']}: unsupported claim "
                  f"'{f['claim']}' -> {f['text']}")
        n = len(all_findings)
        if n:
            print(
                f"\n{n} unsupported completion claim(s). Add evidence "
                "(test output, file path, command result, link, or an "
                "'evidence:' note) next to each claim, or hedge honestly "
                "(UNKNOWN / UNVERIFIED / TODO).",
                file=sys.stderr,
            )
        else:
            print("ok: every completion claim is backed by nearby evidence.")

    return 0 if len(all_findings) <= args.max else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
