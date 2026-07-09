"""Tests for inline noqa and ignore-file suppressions."""
from neo_evidence_gate import check_text
from neo_evidence_gate.cli import main
from neo_evidence_gate.suppress import (
    load_ignore,
    parse_ignore_text,
    line_suppressed,
)


def test_unsuppressed_claim_still_flagged():
    res = check_text("All done.")
    assert not res.ok
    assert res.findings[0].line == 1


def test_inline_noqa_skips_line():
    res = check_text("All done.  # noqa: evidence-gate")
    assert res.ok
    assert res.claims_total == 0


def test_inline_noqa_case_and_spacing():
    assert check_text("Shipped. #NOQA:evidence-gate").ok
    assert check_text("Shipped.  #  noqa:  evidence-gate").ok


def test_inline_noqa_slash_comment():
    assert check_text("Fixed it. // noqa: evidence-gate").ok


def test_inline_noqa_html_comment():
    assert check_text("Ready to ship. <!-- noqa: evidence-gate -->").ok


def test_noqa_only_affects_its_line():
    text = (
        "All done.  # noqa: evidence-gate\n"
        "Everything works now.\n"
    )
    res = check_text(text)
    assert not res.ok
    assert {f.line for f in res.findings} == {2}


def test_line_suppressed_helper():
    assert line_suppressed("x # noqa: evidence-gate")
    assert not line_suppressed("x # noqa: something-else")
    assert not line_suppressed("noqa without marker")


def test_ignore_lines_param():
    res = check_text("All done.", ignore_lines={1})
    assert res.ok


def test_ignore_file_path_line(tmp_path):
    report = tmp_path / "report.md"
    report.write_text("All done.\nStill broken but claimed fixed.\n", encoding="utf-8")
    ignore = tmp_path / ".neo-evidence-gate-ignore"
    # suppress only line 1 of report.md
    ignore.write_text(f"{report.name}:1\n", encoding="utf-8")
    rules = load_ignore(str(ignore))
    res = check_text(
        report.read_text(encoding="utf-8"),
        ignore=rules,
        path=str(report),
    )
    # line 1 suppressed; line 2 still flags "fixed"
    assert not res.ok
    assert all(f.line != 1 for f in res.findings)
    assert any(f.line == 2 for f in res.findings)


def test_ignore_file_whole_path(tmp_path):
    report = tmp_path / "legacy.md"
    report.write_text("All done. Everything works now.\n", encoding="utf-8")
    rules = parse_ignore_text("legacy.md\n")
    res = check_text(
        report.read_text(encoding="utf-8"),
        ignore=rules,
        path=str(report),
    )
    assert res.ok


def test_ignore_file_glob():
    rules = parse_ignore_text("docs/**/old-*.md\n")
    assert rules.suppresses("docs/archive/old-notes.md", 1)
    assert not rules.suppresses("docs/archive/new-notes.md", 1)


def test_ignore_file_comments_and_blanks():
    rules = parse_ignore_text(
        "# comment\n\n"
        "a.md:2\n"
        "  \n"
        "# another\n"
        "b.md\n"
    )
    assert rules.suppresses("a.md", 2)
    assert not rules.suppresses("a.md", 1)
    assert rules.suppresses("b.md", 99)


def test_cli_inline_noqa(tmp_path):
    f = tmp_path / "ok.md"
    f.write_text("All done.  # noqa: evidence-gate\n", encoding="utf-8")
    assert main([str(f)]) == 0


def test_cli_ignore_file(tmp_path):
    report = tmp_path / "report.md"
    report.write_text("All done.\n", encoding="utf-8")
    ignore = tmp_path / "ignore.txt"
    ignore.write_text(f"{report.name}:1\n", encoding="utf-8")
    assert main([str(report), "--ignore-file", str(ignore)]) == 0
    # without ignore file, still fails
    assert main([str(report), "--no-ignore"]) == 1


def test_cli_discovers_ignore_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report = tmp_path / "report.md"
    report.write_text("All done.\n", encoding="utf-8")
    (tmp_path / ".neo-evidence-gate-ignore").write_text(
        "report.md:1\n", encoding="utf-8"
    )
    assert main([str(report)]) == 0
