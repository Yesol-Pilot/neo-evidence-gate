from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import re
import subprocess
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


POLICY_ID = "ng-repo-governance/1.0.0"
ALLOWLIST_NAME = ".github/repository-governance-allowlist.json"
MAX_TEXT_FILE_BYTES = 2_000_000

REQUIRED_SETTINGS: Mapping[str, bool] = {
    "allow_squash_merge": True,
    "allow_merge_commit": False,
    "allow_rebase_merge": False,
    "delete_branch_on_merge": True,
    "allow_update_branch": True,
    "allow_auto_merge": True,
}

APPROVED_DEFAULT_BRANCH_EXCEPTIONS: Mapping[str, str] = {
    "NeoGenesisAI/neomux-desktop": "einstein/main",
}

TASK_BRANCH_PREFIXES: Tuple[str, ...] = (
    "codex/",
    "rebuild/",
    "feature/",
    "fix/",
    "chore/",
    "governance/",
)

ALLOWED_ENV_NAMES: Set[str] = {
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.local.example",
}

FORBIDDEN_NAMES: Set[str] = {
    "credentials.json",
    "service-account.json",
    "service_account.json",
    "cookies.json",
    "session.json",
    "oauth.json",
    "token.json",
}

FORBIDDEN_SUFFIXES: Tuple[str, ...] = (
    ".pem",
    ".p12",
    ".pfx",
    ".keystore",
    ".jks",
    ".mobileprovision",
)

GENERATED_PARTS: Set[str] = {
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".next",
    "coverage",
    "Library",
    "Temp",
    "obj",
    ".gradle",
}

TEXT_EXTENSIONS: Set[str] = {
    ".txt",
    ".md",
    ".json",
    ".jsonc",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".env",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".py",
    ".rb",
    ".php",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".kts",
    ".cs",
    ".swift",
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
    ".xml",
    ".html",
    ".css",
    ".scss",
    ".sql",
    ".gradle",
    ".properties",
    ".conf",
    ".config",
}

SPECIAL_TEXT_NAMES: Set[str] = {"Dockerfile", "Makefile", "Gemfile", "Podfile"}
OBVIOUS_PLACEHOLDER_MARKERS: Tuple[str, ...] = (
    "EXAMPLE",
    "DUMMY",
    "PLACEHOLDER",
    "REDACTED",
    "NOTAREAL",
    "NOT-A-REAL",
    "INVALID",
)


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    severity: str = "error"
    path: Optional[str] = None

    def annotation(self) -> str:
        prefix = "::warning::" if self.severity in {"warning", "blocked"} else "::error::"
        return prefix + self.message


@dataclass(frozen=True)
class SecretRule:
    label: str
    pattern: re.Pattern[str]
    entropy_required: bool = False


@dataclass(frozen=True)
class FixtureException:
    path: str
    blob_sha: str
    labels: Tuple[str, ...]
    reason: str
    owner: str
    expires_at: date

    def matches(self, path: str, blob_sha: str, label: str, today: date) -> bool:
        return (
            today <= self.expires_at
            and self.path == path
            and self.blob_sha == blob_sha
            and label in self.labels
        )


SECRET_RULES: Tuple[SecretRule, ...] = (
    SecretRule(
        "GitHub classic token",
        re.compile(r"(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9]{36,}(?![A-Za-z0-9])"),
        True,
    ),
    SecretRule(
        "GitHub fine-grained token",
        re.compile(r"(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9_]{40,}(?![A-Za-z0-9_])"),
        True,
    ),
    SecretRule(
        "OpenAI secret key",
        re.compile(
            r"(?<![A-Za-z0-9_-])sk-(?:(?:proj|svcacct|admin)-)?[A-Za-z0-9_-]{32,}(?![A-Za-z0-9_-])"
        ),
        True,
    ),
    SecretRule(
        "AWS access key",
        re.compile(r"(?<![0-9A-Z])AKIA[0-9A-Z]{16}(?![0-9A-Z])"),
        True,
    ),
    SecretRule(
        "Google API key",
        re.compile(r"(?<![0-9A-Za-z_-])AIza[0-9A-Za-z_-]{35}(?![0-9A-Za-z_-])"),
        True,
    ),
    SecretRule(
        "Slack token",
        re.compile(r"(?<![0-9A-Za-z-])xox[baprs]-[0-9A-Za-z-]{20,}(?![0-9A-Za-z-])"),
        True,
    ),
    SecretRule(
        "Stripe live secret",
        re.compile(r"(?<![0-9A-Za-z_])sk_live_[0-9A-Za-z]{16,}(?![0-9A-Za-z])"),
        True,
    ),
    SecretRule(
        "Private key header",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
        False,
    ),
)


def _shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts: Dict[str, int] = {}
    for char in value:
        counts[char] = counts.get(char, 0) + 1
    length = float(len(value))
    return -sum((count / length) * math.log(count / length, 2) for count in counts.values())


def _looks_high_entropy(candidate: str) -> bool:
    if len(candidate) < 32:
        return False
    if len(set(candidate)) < 10:
        return False
    classes = 0
    classes += bool(re.search(r"[a-z]", candidate))
    classes += bool(re.search(r"[A-Z]", candidate))
    classes += bool(re.search(r"[0-9]", candidate))
    classes += bool(re.search(r"[_-]", candidate))
    return classes >= 2 and _shannon_entropy(candidate) >= 3.25


def _is_obvious_placeholder(candidate: str) -> bool:
    upper = candidate.upper()
    return any(marker in upper for marker in OBVIOUS_PLACEHOLDER_MARKERS)


def secret_candidates(line: str) -> Iterable[Tuple[str, str]]:
    for rule in SECRET_RULES:
        for match in rule.pattern.finditer(line):
            candidate = match.group(0)
            if _is_obvious_placeholder(candidate):
                continue
            if rule.entropy_required and not _looks_high_entropy(candidate):
                continue
            yield rule.label, candidate


def _is_test_or_fixture_path(path: str) -> bool:
    pure = pathlib.PurePosixPath(path)
    lowered_parts = {part.lower() for part in pure.parts}
    name = pure.name.lower()
    return (
        bool(lowered_parts & {"test", "tests", "__tests__", "fixture", "fixtures"})
        or ".test." in name
        or ".spec." in name
        or name.startswith("test_")
        or name.endswith("_test.py")
        or "test-certificate" in name
    )


def _parse_date(raw: object, field: str) -> date:
    if not isinstance(raw, str):
        raise ValueError(f"{field} must be an ISO date string")
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD") from exc


def load_allowlist(
    root: pathlib.Path, today: Optional[date] = None
) -> Tuple[Set[str], Set[str], Tuple[FixtureException, ...], List[Finding]]:
    current_date = today or date.today()
    path = root / ALLOWLIST_NAME
    if not path.is_file():
        return set(), set(), tuple(), []

    findings: List[Finding] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("root must be an object")
    except Exception as exc:
        return (
            set(),
            set(),
            tuple(),
            [
                Finding(
                    "INVALID_ALLOWLIST",
                    f"invalid governance allowlist: {type(exc).__name__}",
                    path=ALLOWLIST_NAME,
                )
            ],
        )

    allowed_paths = {
        str(value) for value in raw.get("allowedPaths", []) if isinstance(value, str)
    }
    allowed_findings = {
        str(value) for value in raw.get("allowedFindings", []) if isinstance(value, str)
    }

    if allowed_paths:
        findings.append(
            Finding(
                "LEGACY_PATH_ALLOWLIST",
                "legacy allowedPaths bypass is present; replace it with blob-bound syntheticSecretFixtures",
                severity="warning",
                path=ALLOWLIST_NAME,
            )
        )

    fixtures: List[FixtureException] = []
    entries = raw.get("syntheticSecretFixtures", [])
    if not isinstance(entries, list):
        findings.append(
            Finding(
                "INVALID_ALLOWLIST",
                "syntheticSecretFixtures must be an array",
                path=ALLOWLIST_NAME,
            )
        )
        entries = []

    seen_paths: Set[str] = set()
    for index, entry in enumerate(entries):
        prefix = f"syntheticSecretFixtures[{index}]"
        if not isinstance(entry, dict):
            findings.append(
                Finding("INVALID_ALLOWLIST", f"{prefix} must be an object", path=ALLOWLIST_NAME)
            )
            continue
        try:
            fixture_path = entry["path"]
            blob_sha_value = entry["blobSha"]
            labels = entry["labels"]
            reason = entry["reason"]
            owner = entry["owner"]
            expires_at = _parse_date(entry["expiresAt"], f"{prefix}.expiresAt")
            if not isinstance(fixture_path, str) or not fixture_path:
                raise ValueError(f"{prefix}.path must be a non-empty string")
            if fixture_path in seen_paths:
                raise ValueError(f"duplicate synthetic fixture path: {fixture_path}")
            if not _is_test_or_fixture_path(fixture_path):
                raise ValueError(f"synthetic fixture path is not test-like: {fixture_path}")
            if not isinstance(blob_sha_value, str) or not re.fullmatch(
                r"[0-9a-f]{40}", blob_sha_value
            ):
                raise ValueError(f"{prefix}.blobSha must be a lowercase 40-hex Git blob SHA")
            if (
                not isinstance(labels, list)
                or not labels
                or any(not isinstance(label, str) or not label for label in labels)
            ):
                raise ValueError(f"{prefix}.labels must be a non-empty string array")
            unknown_labels = sorted(set(labels) - {rule.label for rule in SECRET_RULES})
            if unknown_labels:
                raise ValueError(f"{prefix}.labels contains unknown labels: {unknown_labels}")
            if not isinstance(reason, str) or len(reason.strip()) < 12:
                raise ValueError(f"{prefix}.reason must explain the fixture")
            if not isinstance(owner, str) or not owner.strip():
                raise ValueError(f"{prefix}.owner must be a non-empty string")
            if expires_at < current_date:
                raise ValueError(f"synthetic fixture exception expired: {fixture_path}")
            seen_paths.add(fixture_path)
            fixtures.append(
                FixtureException(
                    path=fixture_path,
                    blob_sha=blob_sha_value,
                    labels=tuple(labels),
                    reason=reason.strip(),
                    owner=owner.strip(),
                    expires_at=expires_at,
                )
            )
        except (KeyError, ValueError) as exc:
            findings.append(Finding("INVALID_ALLOWLIST", str(exc), path=ALLOWLIST_NAME))

    return allowed_paths, allowed_findings, tuple(fixtures), findings


def validate_repository_settings(
    repository: str,
    settings: Mapping[str, object],
) -> List[Finding]:
    findings: List[Finding] = []
    for key, expected in REQUIRED_SETTINGS.items():
        if key not in settings or settings.get(key) is None:
            findings.append(
                Finding(
                    "BLOCKED_ADMIN_AUDIT",
                    f"repository setting {key} is not observable with the current token; expected {expected}",
                    severity="blocked",
                )
            )
            continue
        actual = settings.get(key)
        if type(actual) is not bool:
            findings.append(
                Finding(
                    "INVALID_SETTINGS_RESPONSE",
                    f"repository setting {key} returned non-boolean type {type(actual).__name__}",
                )
            )
        elif actual != expected:
            findings.append(
                Finding(
                    "SETTINGS_MISMATCH",
                    f"repository setting {key} must be {expected}, got {actual}",
                )
            )

    if "default_branch" not in settings or not settings.get("default_branch"):
        findings.append(
            Finding(
                "BLOCKED_ADMIN_AUDIT",
                "repository default branch is not observable with the current token",
                severity="blocked",
            )
        )
        return findings

    default_branch = str(settings["default_branch"])
    expected_exception = APPROVED_DEFAULT_BRANCH_EXCEPTIONS.get(repository)
    if expected_exception:
        if default_branch != expected_exception:
            findings.append(
                Finding(
                    "DEFAULT_BRANCH_DRIFT",
                    "documented default-branch exception drifted: "
                    f"expected {expected_exception}, got {default_branch}",
                )
            )
    elif default_branch.startswith(TASK_BRANCH_PREFIXES):
        findings.append(
            Finding(
                "TASK_DEFAULT_BRANCH",
                f"task branch is configured as repository default: {default_branch}",
            )
        )
    return findings


def validate_contract(root: pathlib.Path) -> List[Finding]:
    contract = root / "REPOSITORY_GOVERNANCE.md"
    if not contract.is_file():
        return [Finding("MISSING_CONTRACT", "REPOSITORY_GOVERNANCE.md is missing")]
    text = contract.read_text(encoding="utf-8", errors="replace")
    normalized = text.replace("`", "").lower()
    findings: List[Finding] = []
    if POLICY_ID not in text:
        findings.append(
            Finding(
                "INVALID_CONTRACT",
                f"repository contract does not identify policy {POLICY_ID}",
                path="REPOSITORY_GOVERNANCE.md",
            )
        )
    if "unknown" not in normalized or "must never be reported as pass" not in normalized:
        findings.append(
            Finding(
                "INVALID_CONTRACT",
                "repository contract does not define UNKNOWN as non-PASS",
                path="REPOSITORY_GOVERNANCE.md",
            )
        )
    if "presence of this file alone" not in normalized:
        findings.append(
            Finding(
                "INVALID_CONTRACT",
                "repository contract does not prohibit documentation-only compliance",
                path="REPOSITORY_GOVERNANCE.md",
            )
        )
    return findings


def tracked_paths(root: pathlib.Path) -> List[str]:
    output = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "-z"],
        stderr=subprocess.DEVNULL,
    )
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in output.split(b"\0")
        if item
    ]


def blob_sha(root: pathlib.Path, path: str) -> str:
    output = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "-s", "--", path],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()
    if not output:
        return ""
    first = output.splitlines()[0].split()
    return first[1] if len(first) >= 2 else ""


def validate_tracked_paths(paths: Sequence[str]) -> List[Finding]:
    findings: List[Finding] = []
    for raw in paths:
        path = pathlib.PurePosixPath(raw)
        name = path.name
        parts = set(path.parts)
        if name == ".env" or (name.startswith(".env.") and name not in ALLOWED_ENV_NAMES):
            findings.append(
                Finding(
                    "TRACKED_ENVIRONMENT_FILE",
                    f"prohibited environment file is tracked: {raw}",
                    path=raw,
                )
            )
        if name in FORBIDDEN_NAMES or name.endswith(FORBIDDEN_SUFFIXES):
            findings.append(
                Finding(
                    "TRACKED_CREDENTIAL_FILE",
                    f"prohibited credential or signing file is tracked: {raw}",
                    path=raw,
                )
            )
        if parts & GENERATED_PARTS:
            findings.append(
                Finding(
                    "TRACKED_GENERATED_DIRECTORY",
                    f"generated or dependency directory is tracked: {raw}",
                    path=raw,
                )
            )
    return findings


def scan_current_tree_secrets(
    root: pathlib.Path,
    paths: Sequence[str],
    fixture_exceptions: Sequence[FixtureException],
    allowed_paths: Set[str],
    today: Optional[date] = None,
) -> List[Finding]:
    current_date = today or date.today()
    findings: List[Finding] = []
    by_path: Dict[str, List[FixtureException]] = {}
    for exception in fixture_exceptions:
        by_path.setdefault(exception.path, []).append(exception)

    for raw in paths:
        if raw in allowed_paths:
            continue
        path = root / raw
        try:
            if not path.is_file() or path.stat().st_size > MAX_TEXT_FILE_BYTES:
                continue
        except OSError:
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS and path.name not in SPECIAL_TEXT_NAMES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        current_blob = blob_sha(root, raw)
        exceptions = by_path.get(raw, [])
        for line_number, line in enumerate(content.splitlines(), start=1):
            for label, _candidate in secret_candidates(line):
                if any(
                    exception.matches(raw, current_blob, label, current_date)
                    for exception in exceptions
                ):
                    continue
                findings.append(
                    Finding(
                        "CURRENT_TREE_SECRET_PATTERN",
                        f"{label} pattern detected at {raw}:{line_number}",
                        path=raw,
                    )
                )
    return findings


def fetch_repository_settings(
    repository: str, token: str
) -> Tuple[Mapping[str, object], List[Finding]]:
    if not repository or not token:
        return (
            {},
            [
                Finding(
                    "BLOCKED_ADMIN_AUDIT",
                    "repository identity or GitHub token is unavailable",
                    severity="blocked",
                )
            ],
        )
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "neogenesis-repository-governance",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            value = json.load(response)
        if not isinstance(value, dict):
            raise ValueError("repository settings response is not an object")
        return value, []
    except Exception as exc:
        return (
            {},
            [
                Finding(
                    "BLOCKED_ADMIN_AUDIT",
                    f"cannot read repository settings: {type(exc).__name__}",
                    severity="blocked",
                )
            ],
        )


def evaluate(
    root: pathlib.Path,
    repository: str,
    settings: Mapping[str, object],
    initial_findings: Optional[Sequence[Finding]] = None,
    today: Optional[date] = None,
) -> List[Finding]:
    current_date = today or date.today()
    findings: List[Finding] = list(initial_findings or [])
    allowed_paths, allowed_findings, fixtures, allowlist_findings = load_allowlist(
        root, current_date
    )
    findings.extend(allowlist_findings)
    findings.extend(validate_contract(root))
    findings.extend(validate_repository_settings(repository, settings))

    paths = tracked_paths(root)
    findings.extend(validate_tracked_paths(paths))
    findings.extend(
        scan_current_tree_secrets(
            root,
            paths,
            fixtures,
            allowed_paths,
            current_date,
        )
    )

    filtered = [finding for finding in findings if finding.message not in allowed_findings]
    unique: Dict[Tuple[str, str, str, Optional[str]], Finding] = {}
    for finding in filtered:
        key = (finding.code, finding.message, finding.severity, finding.path)
        unique[key] = finding
    return sorted(unique.values(), key=lambda item: (item.severity, item.code, item.message))


def _load_settings_file(path: pathlib.Path) -> Mapping[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("settings file root must be an object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate NeoGenesis repository governance.")
    parser.add_argument("--root", default=".", help="Caller repository working tree.")
    parser.add_argument("--repository", default=os.environ.get("REPOSITORY", ""))
    parser.add_argument(
        "--settings-file",
        help="Read repository settings from a JSON file instead of the GitHub API.",
    )
    parser.add_argument(
        "--defer-admin-audit",
        action="store_true",
        help=(
            "Return success when the only blockers are repository settings hidden "
            "from GITHUB_TOKEN. The JSON summary remains PASS_WITH_BLOCKED_ADMIN_AUDIT."
        ),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root = pathlib.Path(args.root).resolve()
    repository = str(args.repository or "")
    initial: List[Finding] = []

    if args.settings_file:
        try:
            settings = _load_settings_file(pathlib.Path(args.settings_file))
        except Exception as exc:
            settings = {}
            initial.append(
                Finding(
                    "BLOCKED_ADMIN_AUDIT",
                    f"cannot read repository settings file: {type(exc).__name__}",
                    severity="blocked",
                )
            )
    else:
        settings, initial = fetch_repository_settings(
            repository, os.environ.get("GH_TOKEN", "")
        )

    findings = evaluate(root, repository, settings, initial)
    for finding in findings:
        print(finding.annotation())

    errors = [finding for finding in findings if finding.severity == "error"]
    blocked = [finding for finding in findings if finding.severity == "blocked"]
    warnings = [finding for finding in findings if finding.severity == "warning"]

    if errors:
        status = "FAIL"
    elif blocked and args.defer_admin_audit:
        status = "PASS_WITH_BLOCKED_ADMIN_AUDIT"
    elif blocked:
        status = "BLOCKED"
    else:
        status = "PASS"

    summary = {
        "status": status,
        "scope": "current-tree-and-observable-repository-settings",
        "errors": len(errors),
        "blocked": len(blocked),
        "warnings": len(warnings),
    }
    print(json.dumps(summary, sort_keys=True))

    if errors:
        return 1
    if blocked and not args.defer_admin_audit:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
