"""Before/after precision tests for narrative 'done' and --prose mode.

These cases document measurable precision improvements: each narrative
snippet used to (or still would, under a bare ``\\bdone\\b``) look like a
completion claim, and after the tightened patterns / prose mode it must not.
"""
import re

from neo_evidence_gate import check_text
from neo_evidence_gate.cli import main
from neo_evidence_gate.rules import claim_regexes


# ---------------------------------------------------------------------------
# Baseline: bare ``\bdone\b`` *would* fire on these narrative lines.
# ---------------------------------------------------------------------------
_BARE_DONE = re.compile(r"\bdone\b", re.IGNORECASE)

NARRATIVE_FALSE_POSITIVES = [
    "When she was done cooking, she left the kitchen.",
    "Well done on the presentation yesterday.",
    "I've done similar migrations before.",
    "Once you're done with the form, click submit.",
    "He had done nothing wrong that day.",
    "The students were done with their exams by noon.",
]


def test_bare_done_would_match_narrative():
    """Guard: if these stop matching bare done, the before/after is moot."""
    for line in NARRATIVE_FALSE_POSITIVES:
        assert _BARE_DONE.search(line), f"expected bare done in: {line!r}"


def test_default_no_longer_flags_narrative_done():
    """AFTER: tightened default claim set leaves narrative prose alone."""
    for line in NARRATIVE_FALSE_POSITIVES:
        res = check_text(line)
        assert res.ok, (
            f"false positive on narrative line: {line!r} -> "
            f"{[f.as_dict() for f in res.findings]}"
        )


def test_default_still_flags_real_completion_claims():
    """Tightening must not drop agent/status-style claims."""
    real_claims = [
        "All done.",
        "Done!",
        "Done — ready for review.",
        "The payment bug is done.",
        "Status: done",
        "- Signup flow: done.",
        "We're done with the migration.",
        "Everything is done.",
    ]
    for line in real_claims:
        res = check_text(line)
        assert not res.ok, f"missed real claim: {line!r}"


def test_default_still_flags_examples_style_lines():
    # Mirrors examples/bad.md shapes
    assert not check_text("All done. The payment bug is fixed.").ok
    assert not check_text("Login flow works now.").ok
    assert not check_text("Ready to ship — everything verified.").ok
    assert not check_text("Migration completed successfully.").ok


def test_measurement_done_still_backed():
    assert check_text("Done — response time dropped to 42 ms.").ok


# ---------------------------------------------------------------------------
# --prose mode: more conservative on fixed / working / successfully
# ---------------------------------------------------------------------------

PROSE_ONLY_FALSE_POSITIVES = [
    # default may still see these as claims; prose should not
    "She successfully argued her case before the committee.",
    "A fixed income portfolio needs rebalancing.",
    "They were working late on the manuscript.",
    "Please verify your email address to continue.",
]


def test_prose_skips_narrative_non_status_verbs():
    for line in PROSE_ONLY_FALSE_POSITIVES:
        res = check_text(line, prose=True)
        assert res.ok, (
            f"prose mode false positive: {line!r} -> "
            f"{[f.as_dict() for f in res.findings]}"
        )


def test_prose_still_flags_status_claims():
    assert not check_text("All done. Everything works now.", prose=True).ok
    assert not check_text("Ready to ship.", prose=True).ok
    assert not check_text("Migration completed.", prose=True).ok
    assert not check_text("Fixed the login bug.", prose=True).ok
    assert not check_text("Shipped.", prose=True).ok


def test_prose_before_after_fixed_income():
    """Measurable precision: default flags 'fixed'; prose does not."""
    line = "A fixed income portfolio needs rebalancing."
    assert not check_text(line).ok  # before (default still noisy here)
    assert check_text(line, prose=True).ok  # after


def test_prose_before_after_successfully_argued():
    line = "She successfully argued her case before the committee."
    assert not check_text(line).ok
    assert check_text(line, prose=True).ok


def test_claim_regexes_prose_is_smaller_or_equal():
    default_names = {n for n, _ in claim_regexes()}
    prose_names = {n for n, _ in claim_regexes(prose=True)}
    # same family names, different patterns
    assert default_names == prose_names


def test_cli_prose_flag(tmp_path, capsys):
    f = tmp_path / "story.md"
    f.write_text(
        "When she was done cooking, she left.\n"
        "A fixed income note was discussed.\n",
        encoding="utf-8",
    )
    assert main([str(f), "--prose"]) == 0
