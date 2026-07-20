# Work Prompt - RouteDeck

Use this prompt to start, complete, or close RouteDeck work.

## Session Start

```text
I'm working on RouteDeck.

1. Read critical_prompt.md.
2. Read context.md.
3. Read docs/route-deck-reference.md before changing framework meaning.
4. If resuming, read the newest context_checkpoints/ file.
5. Locate the feature in architecture/feature-coverage.md.
6. Review its architecture/code-map.md row and component contract.
7. Review test_index/README.md for focused validation.
8. State current authority, framework/product boundaries, known gaps, and the
   next concrete step.
```

## Feature Completion

```text
The RouteDeck feature is complete.

1. Update docs/route-deck-reference.md if contract meaning changed.
2. Update architecture/feature-coverage.md, architecture/code-map.md, and the
   owning component when coverage or ownership changed.
3. Update SYSTEM_FLOW_INDEX.md when a runtime or UX sequence changed.
4. Update test_index/README.md when validation meaning or commands changed.
5. When one implementation spans several owners, update one verified
   implementation-to-contract-to-proof crosswalk in knowledgebase/.
6. Add an ADR only when a durable future implementation choice changed; an
   accepted ADR may receive a dated implementation-status note without changing
   the decision.
7. Demote completed/superseded plan or design material to docs/archive/.
8. Run the fastest meaningful focused tests.
```

## Session Close

```text
We're wrapping up this RouteDeck session.

1. Add a dated log in logs/.
2. Add a dated checkpoint in context_checkpoints/.
3. Archive the previous context.md in context_history/ when its material state
   changed.
4. Rewrite context.md as the concise live restart snapshot.
5. Name changed files and owning architecture/code-map.md rows.
6. Run python scripts/check_doc_coverage.py.
7. Run python scripts/check_context_architecture.py.
8. Run the fastest meaningful focused validation.
9. Record exact commands/results, runtime location/URL if a service ran, and any
   remaining risk or gap.
10. Do not add downstream implementation during closeout unless requested.
```

## Working Rule

Bootstrap context thinly before implementation; populate full coverage only
after checking live source. Canonical docs describe current behavior, archives
describe history, and test indexes never claim a pass without a current run.
