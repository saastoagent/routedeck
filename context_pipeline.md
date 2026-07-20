# Context Pipeline - RouteDeck

RouteDeck separates durable architecture, current restart state, validation,
and history so an old plan cannot become accidental authority.

## Canonical Layers

### Authority And Contracts

- `critical_prompt.md` - product identity, invariants, authority, stop rules.
- `decisions/` - accepted architectural decisions and supersession history.
- `docs/route-deck-reference.md` - canonical framework vocabulary/semantics.

### Coverage And Ownership

- `architecture/feature-coverage.md` - all live capabilities and their owners,
  code, docs, and focused proof.
- `architecture/code-map.md` - machine-readable subsystem source globs.
- `architecture/components/` - focused subsystem maintenance contracts.
- `architecture/documentation-map.md` - canonical/historical classification.
- `structure.md` - maintained live source tree and dependency direction.

### Flow And Validation

- `SYSTEM_FLOW_INDEX.md` - compact implemented runtime/UX sequences.
- `test_index/README.md` - validation commands and supported claims.

### Current State And Process

- `context.md` - concise live restart snapshot and known gaps.
- `work_prompt.md` - start/completion/closeout prompts.
- `instructions.md` - documentation placement and maintenance rules.
- `context_pipeline.md` - this lifecycle definition.

## Historical Layers

- `context_history/` - prior `context.md` snapshots.
- `context_checkpoints/` - dated session handoffs.
- `logs/` - dated session evidence.
- `docs/archive/` - completed/superseded plans, designs, concepts, reports,
  handoffs, and narrative material.
- `audits/`, `docs/migration/`, `errors/` - point-in-time findings,
  provenance, and debugging evidence.
- `knowledgebase/` - verified reusable findings and cross-owner implementation
  traceability; subordinate to current source and the canonical spine.
- `plans/` - currently active decision-complete plans only.

Historical material never overrides the canonical layers.

## Session Lifecycle

### Start

Read in order:

1. `critical_prompt.md`;
2. `context.md`;
3. `docs/route-deck-reference.md`;
4. newest checkpoint when resuming;
5. `architecture/feature-coverage.md` and owning `code-map.md` row;
6. relevant component contract;
7. `test_index/README.md` and an active plan/skill when applicable.

State the current authority, product/framework boundary, known gap, and next
concrete step before implementation.

### Implement

1. Verify uncertain facts from live source.
2. Change the smallest coherent feature/architecture slice.
3. Keep every changed live source mapped to an ownership row and feature.
4. Update contract, flow, component, and test docs only where meaning moved.
5. Update one knowledgebase implementation crosswalk when a coherent change
   spans several source/documentation owners.
6. Demote completed planning material rather than leaving it active.

### Close

1. Add a dated log and checkpoint.
2. Archive the previous `context.md` when its material state changed.
3. Rewrite `context.md` as the concise current restart snapshot.
4. Run `python scripts/check_doc_coverage.py`.
5. Run `python scripts/check_context_architecture.py`.
6. Run the fastest meaningful focused behavior/boundary validation.
7. Record commands, results, changed ownership rows, and any remaining gap.

## Working Rule

`context.md` links to durable detail; it does not duplicate an architecture
document. Plans explain intended work, never current truth. Test indexes explain
what a command proves, never claim that it passed without a current run.
