# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

### Added
- Composite GitHub Action (`action.yml`) for one-line CI adoption:
  `uses: Yesol-Pilot/neo-evidence-gate@v0` with inputs `files`, `text`,
  `strict`, `max`, `window`, `back`. Documented under README "In CI".

## [0.1.0] - 2026-07-08

Initial public release.

### Added
- Core gate (`check_text`) that flags completion claims lacking nearby evidence.
- Claim / evidence / hedge pattern sets, with a `--strict` broader claim set.
- CLI `neo-evidence-gate` (files or stdin, `--json`, `--window`, `--back`,
  `--max`; CI-friendly exit codes).
- Library API: `check_text`, `GateResult`, `Finding`.
- Test suite and `examples/good.md` / `examples/bad.md`.
