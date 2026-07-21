# RouteDeck Coverage Hardening Plan

**Goal:** Establish an honest coverage baseline and ratchet for the shipped
RouteDeck Python libraries and public TypeScript packages while removing tests
only when current source and contract ownership prove that they are stale or
redundant. Repository-wide 100% coverage is not an M0 launch requirement.

## Coverage contract

- Python reports statements and branches in `routedeck_core`,
  `routedeck_fastapi`, `routedeck_langgraph`, `routedeck_sqlalchemy`, and
  `routedeck_testing`.
- TypeScript reports statements, branches, functions, and lines in all runtime
  source for `packages/core` and `packages/react`.
- Generated contracts, declaration-only files, type-checking-only branches, and
  structurally unreachable abstract protocol bodies are excluded explicitly.
- Medusa remains the reference consumer and keeps its own product coverage
  report; it cannot inflate or satisfy framework package coverage.
- Existing project coverage must not materially regress, and changed critical
  behavior requires focused proof. Small failure-sensitive subsystems may use
  100% local thresholds when every measured branch is meaningful.
- A file that tests a current public contract, failure semantic, architectural
  boundary, or regression is not stale merely because another test executes
  the same source line.

## Stale-test deletion rule

A test may be deleted only when repository evidence shows that its owned
contract or source path was removed or superseded, or when its assertions are
fully duplicated by a stronger current test. Record every deletion and its
replacement proof. Cache files referring to historical test modules are build
debris, not maintained tests.

## Work

- [x] Inventory every maintained test against the test index and current source.
- [x] Delete only tests meeting the stale-test rule; preserve regression and
      boundary tests. No maintained test met the deletion rule; historical
      names were present only in generated caches and an old editable checkout.
- [ ] Close high-value Python statement and branch gaps with behavior-focused
      tests, prioritizing state, supervision, persistence, and transport.
- [ ] Close high-value TypeScript gaps with package-owned tests, prioritizing
      observable state, synchronization, retained requests, and public React
      behavior.
- [ ] Configure coverage reporting and non-regression gates for shipped files;
      keep stricter thresholds scoped to critical subsystems.
- [ ] Run lint, types, builds, package tests, architecture checks, and full
      coverage from a clean report directory.
- [ ] Record exact final counts, exclusions, deletions, and remaining external
      integration boundaries in a session log.

## Stop conditions

- Do not weaken assertions or remove a live failure-path test for percentage
  gains.
- Do not add test-only branches to production code.
- Do not use blanket file exclusions, hide meaningful uncovered modules, or
  count Medusa execution as public-package proof.
- Stop and report if a nominally uncovered branch exposes an ambiguous product
  contract that requires an architectural decision.
- Do not run Git operations, the protected reset, live model tests, or registry
  publication.
