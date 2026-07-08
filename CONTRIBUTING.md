# Contributing to neo-evidence-gate

Thanks for helping. This project is small on purpose; contributions that keep it
small, dependency-free, and honest are the most welcome.

## The one rule

Dogfooding: a PR that claims a fix must show its evidence — a test, command
output, or a file reference. The project runs its own gate on itself. If you
can't show it working, hedge honestly instead (`UNVERIFIED`, `TODO`).

## Setup

```bash
python -m venv venv
# Linux/macOS
source venv/bin/activate
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

pip install -e ".[dev]"
pytest -q
```

No credentials, network, or accounts are needed.

## Layout

- `src/neo_evidence_gate/rules.py` — claim / evidence / hedge patterns
- `src/neo_evidence_gate/gate.py`  — the core scan
- `src/neo_evidence_gate/cli.py`   — the command-line interface
- `tests/` — the test suite (add a case for every behavior change)
- `examples/` — `good.md` passes the gate, `bad.md` fails it

## Making a change

1. Open an issue for anything non-trivial so the approach can be discussed.
   Good first issues are labeled `good first issue`.
2. Branch from `main`: `git checkout -b feat/<short-name>`.
3. Add or update tests. Run `pytest -q` and include the output in your PR.
4. Keep commits scoped (`git add <paths>`, not `git add -A`).
5. Do not add third-party runtime dependencies without discussion — staying
   dependency-free is a feature.

## Tuning patterns

Most contributions are new claim, evidence, or hedge patterns. When you add one:

- prefer precision over recall in the **default** set; put noisier words behind
  `--strict`;
- add a test in `tests/test_gate.py` showing the new pattern matched and, where
  relevant, a near-miss that must *not* match.

## License

By contributing you agree your work is dual-licensed under MIT OR Apache-2.0,
as described in [LICENSE](LICENSE).
