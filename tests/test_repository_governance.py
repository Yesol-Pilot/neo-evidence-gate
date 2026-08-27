from __future__ import annotations

import json
import pathlib
import subprocess
from datetime import date

from neo_evidence_gate.repository_governance import (
    Finding,
    FixtureException,
    evaluate,
    load_allowlist,
    scan_current_tree_secrets,
    secret_candidates,
    validate_repository_settings,
)


def init_repo(tmp_path: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "fixture"], check=True)
    return tmp_path


def current_blob(repo: pathlib.Path, path: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", f"HEAD:{path}"],
        text=True,
    ).strip()


def valid_contract() -> str:
    return """# Repository Governance Contract

Policy ID: `ng-repo-governance/1.0.0`

`UNKNOWN` means not verified and must never be reported as PASS.

The presence of this file alone is not compliance.
"""


def compliant_settings() -> dict[str, object]:
    return {
        "allow_squash_merge": True,
        "allow_merge_commit": False,
        "allow_rebase_merge": False,
        "delete_branch_on_merge": True,
        "allow_update_branch": True,
        "allow_auto_merge": True,
        "default_branch": "main",
    }


def test_openai_pattern_does_not_match_task_identifier() -> None:
    assert list(secret_candidates("task-source-provider-availability")) == []
    assert list(secret_candidates("const sk = 'sk-managed-secret-never-log'")) == []


def test_realistic_secret_shapes_are_detected_without_exposing_values() -> None:
    line = (
        "openai=sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789ABCDEFGH "
        "github=ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AB"
    )
    labels = {label for label, _ in secret_candidates(line)}
    assert labels == {"OpenAI secret key", "GitHub classic token"}


def test_obvious_provider_examples_are_not_treated_as_live_secrets() -> None:
    assert list(secret_candidates("AKIAIOSFODNN7EXAMPLE")) == []
    assert list(secret_candidates("sk-proj-PLACEHOLDER0123456789ABCDEFGHIJKLMNOP")) == []


def test_settings_unknown_is_blocked_not_mismatch() -> None:
    findings = validate_repository_settings("owner/repo", {"default_branch": "main"})
    assert findings
    assert {finding.code for finding in findings} == {"BLOCKED_ADMIN_AUDIT"}
    assert all(finding.severity == "blocked" for finding in findings)


def test_settings_mismatch_is_explicit_error() -> None:
    settings = compliant_settings()
    settings["allow_merge_commit"] = True
    findings = validate_repository_settings("owner/repo", settings)
    assert [(finding.code, finding.severity) for finding in findings] == [
        ("SETTINGS_MISMATCH", "error")
    ]


def test_documented_einstein_default_branch_exception() -> None:
    settings = compliant_settings()
    settings["default_branch"] = "einstein/main"
    assert validate_repository_settings("NeoGenesisAI/neomux-desktop", settings) == []


def test_blob_bound_fixture_exception_suppresses_only_exact_blob(tmp_path: pathlib.Path) -> None:
    repo = init_repo(
        tmp_path,
        {
            "REPOSITORY_GOVERNANCE.md": valid_contract(),
            "tests/redactor.test.ts": (
                "const value = 'sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789ABCDEFGH'\n"
            ),
        },
    )
    blob = current_blob(repo, "tests/redactor.test.ts")
    exception = FixtureException(
        path="tests/redactor.test.ts",
        blob_sha=blob,
        labels=("OpenAI secret key",),
        reason="Synthetic redactor fixture bound to immutable blob.",
        owner="security",
        expires_at=date(2027, 8, 27),
    )
    findings = scan_current_tree_secrets(
        repo,
        ["tests/redactor.test.ts"],
        [exception],
        set(),
        today=date(2026, 8, 28),
    )
    assert findings == []

    (repo / "tests/redactor.test.ts").write_text(
        "const value = 'sk-proj-ZyXwVuTsRqPoNmLkJiHgFeDcBa9876543210HGFEDCBA'\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "tests/redactor.test.ts"], check=True)
    findings = scan_current_tree_secrets(
        repo,
        ["tests/redactor.test.ts"],
        [exception],
        set(),
        today=date(2026, 8, 28),
    )
    assert len(findings) == 1
    assert findings[0].code == "CURRENT_TREE_SECRET_PATTERN"


def test_invalid_or_expired_fixture_exception_fails_closed(tmp_path: pathlib.Path) -> None:
    repo = init_repo(
        tmp_path,
        {
            "REPOSITORY_GOVERNANCE.md": valid_contract(),
            ".github/repository-governance-allowlist.json": json.dumps(
                {
                    "syntheticSecretFixtures": [
                        {
                            "path": "src/production.ts",
                            "blobSha": "a" * 40,
                            "labels": ["OpenAI secret key"],
                            "reason": "Too broad production exception.",
                            "owner": "security",
                            "expiresAt": "2025-01-01",
                        }
                    ]
                }
            ),
        },
    )
    _, _, fixtures, findings = load_allowlist(repo, today=date(2026, 8, 28))
    assert fixtures == ()
    assert findings
    assert all(finding.code == "INVALID_ALLOWLIST" for finding in findings)


def test_evaluate_passes_clean_repository(tmp_path: pathlib.Path) -> None:
    repo = init_repo(
        tmp_path,
        {
            "REPOSITORY_GOVERNANCE.md": valid_contract(),
            "src/app.py": "print('ok')\n",
        },
    )
    assert evaluate(
        repo,
        "owner/repo",
        compliant_settings(),
        today=date(2026, 8, 28),
    ) == []


def test_evaluate_keeps_api_blocker_separate_from_content_findings(
    tmp_path: pathlib.Path,
) -> None:
    repo = init_repo(
        tmp_path,
        {
            "REPOSITORY_GOVERNANCE.md": valid_contract(),
            "src/app.py": "print('ok')\n",
        },
    )
    findings = evaluate(
        repo,
        "owner/repo",
        {"default_branch": "main"},
        initial_findings=[
            Finding(
                "BLOCKED_ADMIN_AUDIT",
                "cannot read repository settings: HTTPError",
                severity="blocked",
            )
        ],
        today=date(2026, 8, 28),
    )
    assert not [finding for finding in findings if finding.severity == "error"]
    assert [finding for finding in findings if finding.severity == "blocked"]
