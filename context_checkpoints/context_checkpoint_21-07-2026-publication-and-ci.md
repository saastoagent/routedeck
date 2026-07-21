# Context Checkpoint - 21-07-2026 Public Source And CI

Project: RouteDeck
Status: M0 public source launch complete; registry package release pending
Runtime boundary: local Windows; protected stack stopped

## Read Next

1. `critical_prompt.md`
2. `context.md`
3. `decisions/ADR-006-framework-owned-runtime-and-conversation-boundary.md`
4. `docs/route-deck-reference.md`
5. `architecture/feature-coverage.md`
6. `architecture/code-map.md`
7. `test_index/README.md`
8. `plans/2026-07-21-coverage-hardening.md`

## Completed

- Published the prepared public-alpha source to
  `https://github.com/saastoagent/routedeck`.
- Migrated the local checkout to that repository as its sole remote after
  first updating the former remote as requested.
- Preserved repository-scoped commit identity
  `raghavdasila@saastoagent.com`.
- Corrected the first clean-checkout CI failures without publishing local
  evidence or weakening validation.
- Proved the replacement GitHub Actions run green for both Python and
  TypeScript, including archive inspection.
- Archived the completed public-alpha implementation plan and the prior
  pre-publication context snapshot.

## Current Proof

- Public-alpha commit: `7d71e4471778abdb5e44c7b642ac0e06227d1dbe`.
- CI correction: `6ec2d6d94009fdc1df98f2360b598775405d810c`.
- Green run:
  `https://github.com/saastoagent/routedeck/actions/runs/29831749835`.
- Documentation coverage: 596/596 maintained live files mapped.
- Context architecture: 43 active Markdown files passed.
- Active-authority tests: 4 passed.

## Active Work

The coverage-hardening plan remains active. Repository-wide 100% coverage is
not an M0 release gate; prioritize failure-sensitive state, supervision,
persistence, transport, synchronization, and public React behavior.

## Remaining M0 Release Work

- Establish PyPI/npm package ownership and trusted publishers.
- Choose alpha versions, publish, and verify clean registry installs.
- Keep the protected reset/full release harness separately approval-gated.
- Do not claim registry availability until published artifacts are installed
  successfully from the registries.
