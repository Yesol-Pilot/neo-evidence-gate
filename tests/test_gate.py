from neo_evidence_gate import check_text
from neo_evidence_gate.cli import main


def test_backed_claim_passes():
    text = "Fixed the parser bug.\n$ pytest -q\n12 passed in 0.3s"
    res = check_text(text)
    assert res.ok, [f.as_dict() for f in res.findings]


def test_unbacked_claim_flagged():
    res = check_text("All done. Everything works now.")
    assert not res.ok
    assert res.findings[0].line == 1


def test_hedge_line_skipped():
    # honest uncertainty is never a violation
    assert check_text("This is probably fixed but UNVERIFIED.").ok
    assert check_text("Done-ish, but not yet tested.").ok


def test_evidence_via_file_path():
    assert check_text("Verified the change in src/app/main.py:42.").ok


def test_evidence_via_url():
    assert check_text("Deployed. See https://example.com/build/123").ok


def test_evidence_via_measurement():
    assert check_text("Done — response time dropped to 42 ms.").ok


def test_adjacent_claims_do_not_share_evidence():
    # line 2 is backed by "5 passed"; line 3 must NOT borrow it (back=0)
    text = (
        "Task report:\n"
        "- Login flow: done. tests pass (5 passed).\n"
        "- Signup flow: done.\n"
    )
    res = check_text(text)
    flagged = {f.line for f in res.findings}
    assert 3 in flagged
    assert 2 not in flagged


def test_forward_window_reaches_code_block():
    text = "Ready to ship.\n\n```\n$ npm test\n0 failures\n```"
    assert check_text(text, window=5).ok


def test_finding_shape():
    res = check_text("done.")
    d = res.findings[0].as_dict()
    assert set(d) >= {"line", "text", "claim", "reason"}


def test_strict_adds_words():
    # "resolved" only counts as a claim in strict mode
    assert check_text("The ticket is resolved.").ok is True
    assert check_text("The ticket is resolved.", strict=True).ok is False


def test_cli_exit_code(tmp_path, capsys):
    good = tmp_path / "good.md"
    good.write_text("Fixed it.\n$ pytest\n3 passed\n", encoding="utf-8")
    bad = tmp_path / "bad.md"
    bad.write_text("All done.\n", encoding="utf-8")

    assert main([str(good)]) == 0
    assert main([str(bad)]) == 1


def test_cli_json(tmp_path, capsys):
    bad = tmp_path / "bad.md"
    bad.write_text("Shipped.\n", encoding="utf-8")
    rc = main([str(bad), "--json"])
    out = capsys.readouterr().out
    assert rc == 1
    assert '"total": 1' in out
