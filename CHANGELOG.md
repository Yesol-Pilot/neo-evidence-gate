# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

### Added
- Inline suppression via `# noqa: evidence-gate` (also `//` and HTML comments)
  so a specific known claim can be accepted without widening the rules.
- Optional ignore file (`.neo-evidence-gate-ignore` or `--ignore-file`):
  `path:line` entries and path globs. CLI: `--no-ignore`.

## [0.1.0] - 2026-07-08

Initial public release.

### Added
- Core gate (`check_text`) that flags completion claims lacking nearby evidence.
- Claim / evidence / hedge pattern sets, with a `--strict` broader claim set.
- CLI `neo-evidence-gate` (files or stdin, `--json`, `--window`, `--back`,
  `--max`; CI-friendly exit codes).
- Library API: `check_text`, `GateResult`, `Finding`.
- Test suite and `examples/good.md` / `examples/bad.md`.
