# Repository Governance Contract

Policy ID: `ng-repo-governance/1.0.0`
Last reviewed: 2026-08-27

## Identity

- Repository: `Yesol-Pilot/neo-evidence-gate`
- Lifecycle class: `verification-policy-tooling`
- Current owner: `Yesol-Pilot`
- Intended owner: `NeoGenesisAI`
- Canonical branch: `main`
- Visibility: `public`
- Production status: `UNKNOWN`
- Transfer state: `REQUIRED`

`UNKNOWN` means not independently verified and must never be reported as PASS.

## Purpose and current risk

Neo Evidence Gate defines or executes company evidence policies. It is a critical trust component: policy, schema, implementation, evidence bytes, actors, target environment, and verdict must remain bound and independently reproducible.

- Active consumers, policy versions, accepted evidence classes, trust roots, deployment, and compatibility remain `UNKNOWN`.
- A producer must not self-author approval, checks, or exemption fields that the gate trusts.
- Missing, skipped, unavailable, stale, simulated, or different-commit evidence must not collapse into PASS.
- Exceptions require owner, scope, reason, compensating controls, start, expiry, and removal condition.

## Required remediation

- [ ] Document policy versions, accepted evidence, forbidden states, actor roles, canonicalization, exact-object rules, exit codes, and consumers.
- [ ] Run full-history secret, dependency, license, public-fixture, and supply-chain audits.
- [ ] Add strict parser, unknown and duplicate field, Unicode alias, actor independence, stale, replay, skipped, unavailable, simulation, exact commit and tree, artifact digest, path containment, timeout, output-size, redaction, exception-expiry, and rollback tests.
- [ ] Separate evidence producer, gate implementation, hostile verifier, policy approver, and release consumer.
- [ ] Bind each verdict to policy version, repository, commit, tree, artifact, environment, actor, command or target action, raw evidence digest, and limitations.
- [ ] Transfer the repository to `NeoGenesisAI` while preserving public consumers and redirects.

## Pull-request and branch rules

- One task, one branch, one isolated worktree.
- Draft inactivity limit: 14 days; maximum stack depth: 3.
- Ready WIP limit: 5; Draft WIP limit: 10.
- PRs declare policy, schema, trust, actor, exception, consumer compatibility, migration, and rollback impact.
- Review conversations resolve before squash merge.
- `main` is not force-pushed or deleted.

## Exit criteria

The repository becomes `TRANSFERRED_COMPLIANT` only when organization ownership, explicit policy and trust model, hostile exact-object verification, expiring exceptions, independent actors, immutable verdict receipts, consumer compatibility, and rollback are proven.

The presence of this file alone is not compliance.
