# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

### Changed
- Tighten default `done` / `working` claim patterns so narrative uses
  ("when she was done cooking", "well done", "I've done …") are not flagged.

### Added
- `--prose` mode (and `check_text(..., prose=True)`) with a more conservative
  claim set for long-form / narrative text. Before/after precision tests in
  `tests/test_prose.py`.

## [0.1.0] - 2026-07-08

Initial public release.

### Added
- Core gate (`check_text`) that flags completion claims lacking nearby evidence.
- Claim / evidence / hedge pattern sets, with a `--strict` broader claim set.
- CLI `neo-evidence-gate` (files or stdin, `--json`, `--window`, `--back`,
  `--max`; CI-friendly exit codes).
- Library API: `check_text`, `GateResult`, `Finding`.
- Test suite and `examples/good.md` / `examples/bad.md`.
