# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-07-12

Initial public release.

### Added
- `.pre-commit-hooks.yaml` so the gate installs as a first-class pre-commit
  repo (`neo-evidence-gate` for files, `neo-evidence-gate-commit-msg` for
  commit messages). Documented `repo: https://github.com/Yesol-Pilot/neo-evidence-gate`
  usage in the README.
- Core gate (`check_text`) that flags completion claims lacking nearby evidence.
- Claim / evidence / hedge pattern sets, with a `--strict` broader claim set.
- CLI `neo-evidence-gate` (files or stdin, `--json`, `--window`, `--back`,
  `--max`; CI-friendly exit codes).
- Library API: `check_text`, `GateResult`, `Finding`.
- Test suite and `examples/good.md` / `examples/bad.md`.
