# neo-evidence-gate

**An honesty linter for completion claims.** It flags lines that say a task is
*done* — `DONE`, `PASS`, `READY`, `VERIFIED`, `fixed`, `works now`, `shipped` —
when there is **no evidence** next to the claim.

Built for the age of AI agents, where "✅ Done!" is cheap and proof is not.
Point it at agent output, pull-request descriptions, commit messages, or task
reports, and it tells you which claims are unsupported.

```
$ neo-evidence-gate examples/bad.md
examples/bad.md:3: unsupported claim 'done' -> - All done. The payment bug is fixed.
examples/bad.md:4: unsupported claim 'working' -> - Login flow works now.
examples/bad.md:5: unsupported claim 'ready to ship' -> - Ready to ship — everything verified.
examples/bad.md:6: unsupported claim 'completed' -> - Migration completed successfully.

4 unsupported completion claim(s). Add evidence (test output, file path,
command result, link, or an 'evidence:' note) next to each claim, or hedge
honestly (UNKNOWN / UNVERIFIED / TODO).
```

## Why

An assistant that writes `All tests pass ✅` without running them is not lying on
purpose — it is pattern-matching what a finished task *sounds like*. The fix is
structural: make the claim carry its receipt. `neo-evidence-gate` is a tiny,
dependency-free gate you can drop into CI or a pre-commit hook so that a claim
of "done" has to travel with a test result, a file path, a command output, a
link, or an explicit `evidence:` note — otherwise the build goes red.

It is the same discipline good engineers already apply to each other's PRs,
turned into a command you can run.

## Install

```bash
pip install neo-evidence-gate
```

Requires Python 3.9+. No third-party runtime dependencies.

## Use

```bash
# check files
neo-evidence-gate report.md notes.md

# check a commit message or an agent's answer from stdin
git log -1 --pretty=%B | neo-evidence-gate -
echo "All done, everything works" | neo-evidence-gate -

# machine-readable
neo-evidence-gate report.md --json

# broaden the claim vocabulary (more matches, more noise)
neo-evidence-gate report.md --strict
```

Exit code is `0` when the number of findings is `<= --max` (default `0`), and
`1` otherwise — so it drops straight into CI.

### As a library

```python
from neo_evidence_gate import check_text

result = check_text("Fixed it.\n$ pytest\n12 passed")
print(result.ok)          # True
for f in result.findings: # []  (nothing unsupported)
    print(f.as_dict())
```

### In CI (GitHub Actions)

```yaml
- name: Evidence gate on the PR body
  run: |
    pip install neo-evidence-gate
    printf '%s' "${{ github.event.pull_request.body }}" | neo-evidence-gate -
```

### As a pre-commit hook

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: neo-evidence-gate
      name: evidence gate (commit message)
      entry: neo-evidence-gate
      language: system
      stages: [commit-msg]
```

## How it works

For every line, the gate:

1. **Skips honest hedges.** A line containing `UNKNOWN`, `UNVERIFIED`, `TODO`,
   `not yet tested`, `probably`, `assume`, `should`, `might`, `WIP`, ... is never
   a violation. Saying "I'm not sure" is the opposite of a false claim.
2. **Detects a completion claim** (`done`, `tests pass`, `verified`, `fixed`,
   `ready to ship`, ...).
3. **Looks for evidence** on that line and in a short window *after* it:
   a fenced code block, a shell-prompt line, a URL, an inline code span, a file
   path, a numeric result (`12 passed`, `0 errors`, `exit code 0`, `180 ms`), or
   an explicit `evidence:` / `output:` / `readback:` lead-in.
4. If the claim has no nearby evidence, it is **flagged**.

Evidence is looked for *after* the claim by default (`--back 0`): the habit the
gate teaches is "state the claim, then show the proof."

## Honest limitations

This is a **heuristic linter**, not a proof checker — and it is upfront about
that, because a tool about honesty should be honest.

- It cannot tell whether the evidence is *real*, only whether *some* concrete
  evidence sits next to the claim. It raises the floor; it does not verify truth.
- Natural-language claim detection has false positives (a stray "done" in prose)
  and false negatives (a novel way to say "finished"). Tune with `--strict`,
  `--window`, and `--back`, or hedge lines you don't want scanned.
- It is tuned for completion-report text (agent output, PRs, commits, task
  logs), not arbitrary prose.

## License

Dual-licensed under **MIT OR Apache-2.0**, at your option — see
[LICENSE](LICENSE). Contributions are accepted under the same terms.

---

`neo-evidence-gate` is part of [Neo Genesis](https://neogenesis.app), where the
same principle governs the agent runtime itself: no `DONE` without evidence.
