# RouteDeck Context Architecture And Coverage Design

Status: implemented and archived on 2026-07-17

## Goal

Make the repository explain its live architecture without requiring transcript,
plan, or source archaeology. Canonical documentation must cover every supported
framework and Medusa reference capability, while superseded execution material
is visibly historical and dead paths are removed only when their lack of live
ownership is proven.

## Canonical Spine

The maintained reading order is:

1. `critical_prompt.md` for invariants and authority;
2. `context.md` for the concise restart snapshot;
3. `docs/route-deck-reference.md` for contract meaning;
4. `architecture/feature-coverage.md` for end-to-end capability coverage;
5. `architecture/code-map.md` and `architecture/components/` for ownership;
6. `SYSTEM_FLOW_INDEX.md` for runtime sequences;
7. `test_index/README.md` for proof boundaries;
8. `architecture/documentation-map.md` for canonical versus historical status.

No plan, handoff, transcript, audit, generated artifact, or context checkpoint
may override that spine.

## Archive Policy

- Accepted ADRs remain in `decisions/` with explicit supersession notes.
- Completed or superseded plans and designs move under `docs/archive/`.
- Historical reports, old product concepts, and handoffs move under named
  archive categories.
- Context history, checkpoints, logs, audits, errors, and migration provenance
  remain in their already historical lifecycle folders.
- Archive material is preserved as evidence and may contain obsolete commands
  or paths. Its archive banner and index must prevent it from being mistaken for
  current instructions.

## Deletion Policy

Delete only material that has no live source, package, import, test, unique
evidence, or historical value. Generated caches and empty legacy roots qualify.
Videos, release artifacts, conversation archives, accepted ADRs, and audit
evidence do not.

## Coverage Contract

`architecture/feature-coverage.md` maps each live capability to:

- framework and consumer ownership;
- implementation roots;
- public interfaces;
- canonical documentation;
- focused proof.

`architecture/code-map.md` remains the machine-readable source-glob ownership
table. The documentation checker must support explicit files and whole-tree
coverage without implicitly invoking Git.

## Validation

Closeout uses focused documentation/authority checks, public API and boundary
tests, and static import/link validation. This documentation cleanup does not
require a live commerce stack or full checkout E2E.
