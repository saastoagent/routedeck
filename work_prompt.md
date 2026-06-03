# Work Prompt - RouteDeck

Use this prompt to start, resume, or close RouteDeck work.

## Session Start Prompt

```text
I'm working on RouteDeck.

Please:
1. Read critical_prompt.md first.
2. Read context.md for the current restart snapshot.
3. Read docs/route-deck-reference.md before changing framework terms, schemas, surfaces, navgraph, capabilities, or product examples.
4. If resuming, inspect the latest context_checkpoints/ file.
5. Review architecture/code-map.md before changing source files, tests, examples, package metadata, or architecture docs.
6. Review test_index/README.md for validation commands.
7. State the current state, the active boundary constraints, and the next concrete step.
```

## Session End Prompt

```text
We're wrapping up this RouteDeck session. Please:

1. Create a log entry in logs/.
2. Create a checkpoint in context_checkpoints/.
3. Archive the previous context.md into context_history/ if context.md materially changes.
4. Rewrite context.md as the concise live restart snapshot.
5. Name changed files and their owning architecture/code-map.md subsystem rows.
6. Update related component docs, test_index, decisions, knowledgebase, docs, or plans when contracts move; otherwise state why they are unchanged.
7. Run python scripts/check_doc_coverage.py and capture notable warnings.
8. Run the fastest meaningful validation command for the changed area.
9. Do not implement downstream code changes during closeout unless explicitly requested.
```

## Feature Completion Prompt

```text
The RouteDeck feature is complete. Please:

1. Update docs/ and docs/route-deck-reference.md if framework meaning changed.
2. Update architecture/code-map.md and relevant architecture/components/ docs if ownership, interfaces, tests, or update triggers changed.
3. Update SYSTEM_FLOW_INDEX.md if runtime or UX flows changed.
4. Update test_index/README.md with validation meaning and commands.
5. Update context.md and add a checkpoint.
6. Add an ADR in decisions/ when a choice changes future implementation.
```

## Current Working Rule

Do a thin context bootstrap before major downstream alignment work. Full context
population comes after the codebase is aligned with `docs/route-deck-reference.md`
so the handoff does not canonize stale implementation details.
