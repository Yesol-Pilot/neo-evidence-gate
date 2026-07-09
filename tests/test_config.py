"""Tests for project config loading and pattern merging."""
from pathlib import Path

import pytest

from neo_evidence_gate import check_text
from neo_evidence_gate.cli import main
from neo_evidence_gate.config import GateConfig, load_config, toml_available
from neo_evidence_gate.rules import claim_regexes, evidence_regexes, hedge_regexes


pytestmark = pytest.mark.skipif(
    not toml_available(),
    reason="tomllib/tomli not available",
)


def test_claims_add_extends_defaults():
    cfg = GateConfig(claims_add=[("ship_it", r"\bship it\b")])
    # Built-in still works
    res = check_text("All done.", config=cfg)
    assert not res.ok
    # Custom claim is detected
    res2 = check_text("Ready — ship it!", config=cfg)
    assert not res2.ok
    assert "ship it" in res2.findings[0].claim.lower()


def test_claims_replace_drops_defaults():
    cfg = GateConfig(
        claims_add=[("ship_it", r"\bship it\b")],
        claims_replace=True,
    )
    # Default "done" is no longer a claim
    assert check_text("All done.", config=cfg).ok
    # Custom claim still fires
    assert not check_text("Please ship it now.", config=cfg).ok


def test_evidence_add_backs_custom_signal():
    cfg = GateConfig(evidence_add=[r"\bLGTM\b"])
    # Without config, LGTM is not evidence
    assert not check_text("Fixed the bug. LGTM").ok
    # With config, it is
    assert check_text("Fixed the bug. LGTM", config=cfg).ok


def test_hedges_add_skips_line():
    cfg = GateConfig(hedges_add=[r"\bPENDING_REVIEW\b"])
    assert not check_text("Done and shipped.").ok
    assert check_text("Done and shipped. PENDING_REVIEW", config=cfg).ok


def test_merged_claim_regexes_count():
    base = claim_regexes()
    extended = claim_regexes(extra=[("x", r"\bx\b")])
    assert len(extended) == len(base) + 1
    replaced = claim_regexes(extra=[("x", r"\bx\b")], replace=True)
    assert len(replaced) == 1


def test_load_dedicated_toml(tmp_path, monkeypatch):
    cfg_path = tmp_path / ".neo-evidence-gate.toml"
    cfg_path.write_text(
        'claims_add = [["ship_it", "\\\\bship it\\\\b"]]\n'
        'evidence_add = ["\\\\bLGTM\\\\b"]\n'
        'hedges_add = ["\\\\bPENDING\\\\b"]\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.source and cfg_path.name in cfg.source
    assert cfg.claims_add == [("ship_it", r"\bship it\b")]
    assert cfg.evidence_add == [r"\bLGTM\b"]
    assert cfg.hedges_add == [r"\bPENDING\b"]


def test_load_pyproject_table(tmp_path, monkeypatch):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname = \"demo\"\nversion = \"0\"\n\n"
        "[tool.neo-evidence-gate]\n"
        'claims_add = [["custom", "\\\\bCUSTOM_DONE\\\\b"]]\n'
        "claims_replace = false\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.claims_add == [("custom", r"\bCUSTOM_DONE\b")]
    res = check_text("Status: CUSTOM_DONE", config=cfg)
    assert not res.ok


def test_load_explicit_path(tmp_path):
    cfg_path = tmp_path / "my.toml"
    cfg_path.write_text(
        'evidence_add = ["\\\\bOK_BY_POLICY\\\\b"]\n',
        encoding="utf-8",
    )
    cfg = load_config(str(cfg_path), required=True)
    assert check_text("Shipped. OK_BY_POLICY", config=cfg).ok


def test_cli_with_config(tmp_path, capsys):
    cfg_path = tmp_path / ".neo-evidence-gate.toml"
    cfg_path.write_text(
        'evidence_add = ["\\\\bLGTM\\\\b"]\n',
        encoding="utf-8",
    )
    report = tmp_path / "report.md"
    report.write_text("Fixed the login flow. LGTM\n", encoding="utf-8")
    assert main([str(report), "--config", str(cfg_path)]) == 0


def test_cli_no_config_ignores_file(tmp_path, monkeypatch):
    cfg_path = tmp_path / ".neo-evidence-gate.toml"
    cfg_path.write_text(
        'evidence_add = ["\\\\bLGTM\\\\b"]\n',
        encoding="utf-8",
    )
    report = tmp_path / "report.md"
    report.write_text("Fixed the login flow. LGTM\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # With discovery, LGTM backs the claim
    assert main([str(report)]) == 0
    # With --no-config, LGTM is not evidence
    assert main([str(report), "--no-config"]) == 1


def test_claim_dict_form_in_toml(tmp_path):
    cfg_path = tmp_path / "cfg.toml"
    cfg_path.write_text(
        "[[claims_add]]\n"
        'name = "all_green"\n'
        'pattern = "\\\\ball green\\\\b"\n',
        encoding="utf-8",
    )
    cfg = load_config(str(cfg_path), required=True)
    assert cfg.claims_add == [("all_green", r"\ball green\b")]
    assert not check_text("Dashboard is all green.", config=cfg).ok


def test_evidence_and_hedge_helpers():
    assert len(evidence_regexes(extra=[r"\bX\b"])) > len(evidence_regexes())
    assert len(evidence_regexes(extra=[r"\bX\b"], replace=True)) == 1
    assert len(hedge_regexes(extra=[r"\bY\b"])) > len(hedge_regexes())
    assert len(hedge_regexes(extra=[r"\bY\b"], replace=True)) == 1
