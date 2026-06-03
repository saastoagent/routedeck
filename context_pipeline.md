# Context Pipeline - RouteDeck

RouteDeck uses a structured context pipeline for continuity, planning,
code-referenced architecture, and clean handoffs.

## Layers

### Vision

- `critical_prompt.md` - stable north star and boundaries.
- `docs/route-deck-reference.md` - canonical framework reference.

### State

- `context.md` - concise live restart snapshot.
- `context_history/` - archived prior `context.md` snapshots.
- `context_checkpoints/` - end-of-session handoff snapshots.
- `structure.md` - maintained project tree and source ownership snapshot.

### Process

- `instructions.md` - documentation workflow.
- `work_prompt.md` - session start/end prompts.
- `context_pipeline.md` - this file.

### Architecture And Validation

- `architecture/code-map.md` - source-to-doc/test ownership map.
- `architecture/components/` - focused component contracts.
- `SYSTEM_FLOW_INDEX.md` - compact runtime and UX flow index.
- `test_index/README.md` - validation ownership and commands.

### History, Decisions, And Knowledge

- `logs/` - session activity history.
- `decisions/` - ADRs for durable implementation choices.
- `knowledgebase/` - verified reusable findings.
- `plans/` - active plans that are not already under `docs/superpowers/plans/`.
- `audits/` - read-only audit reports.
- `errors/` - resolved hard debugging notes.
- `skills/` - reusable workflows only.

## Session Lifecycle

### Start

Read, in order:

1. `critical_prompt.md`
2. `context.md`
3. `docs/route-deck-reference.md`
4. Latest `context_checkpoints/` file if resuming
5. `architecture/code-map.md` when source, tests, examples, or docs are in scope
6. Relevant `architecture/components/` doc
7. Relevant plan or repo-local skill

### Plan

1. Verify uncertain facts from the repo.
2. Keep product and framework boundaries explicit.
3. Use the locked reference for framework meaning.
4. Record durable choices in `decisions/` when they affect future work.

### Implement

1. Change the smallest coherent slice.
2. Track changed files against `architecture/code-map.md`.
3. Update docs/tests only where contracts moved.
4. Keep `context.md` concise and current.

### Close

1. Create a log in `logs/`.
2. Create a checkpoint in `context_checkpoints/`.
3. Archive old `context.md` into `context_history/` if materially changed.
4. Rewrite `context.md` as the current restart snapshot.
5. Run `python scripts/check_doc_coverage.py`.
6. Run the fastest meaningful validation command.

## Working Rule

Do not turn `context.md` into an architecture document. Put durable framework
meaning in `docs/route-deck-reference.md`, subsystem ownership in
`architecture/`, and validation meaning in `test_index/`.
