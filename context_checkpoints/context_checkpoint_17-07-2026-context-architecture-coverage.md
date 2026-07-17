# Context Checkpoint - 17-07-2026

Project: RouteDeck
Status: context architecture coverage and stale-material cleanup complete
Runtime boundary: local Windows only

## Current Authority

ADR-006 controls framework runtime and generic conversation ownership;
non-superseded ADR-005 controls feature/state structure; ADR-004 controls scope,
the Medusa/product boundary, and local execution.

Read next:

1. `critical_prompt.md`
2. `context.md`
3. `docs/route-deck-reference.md`
4. `architecture/feature-coverage.md`
5. `architecture/code-map.md`
6. `SYSTEM_FLOW_INDEX.md`
7. `test_index/README.md`

## Implemented Reality

- Developers author `Feature` modules with complete nodes and node-owned
  outgoing transitions; `Application` composition only selects features and an
  entry node.
- RouteDeck owns one compiled/runtime/session/supervision/navigation/
  conversation/browser state path. Products own domain behavior, APIs,
  prompts/models/graphs, authentication, and UI.
- Medusa is the real local reference consumer for catalog, cart, checkout,
  orders, hybrid chat/surfaces, deep links, review, and confirmation.
- Missing/expired/contract-stale guest bootstrap creates a session only for a
  captured shareable route; session-bound routes do not create replacement
  state.
- The Medusa guest selector is one HTTP-only cookie. Authenticated user/tenant
  and multi-session authorization remains future consumer/adapter work.

## Documentation State

- Full feature-to-owner/code/doc/test coverage is in
  `architecture/feature-coverage.md`.
- Canonical versus historical classification is in
  `architecture/documentation-map.md`.
- Completed plans/designs and retired concepts are under `docs/archive/`.
- The prior live context is preserved as
  `context_history/20260717_context_before_context_architecture_coverage.md`.
- Git-independent coverage and context/link checkers are available under
  `scripts/`.

## Focused Proof

- 562 maintained live source files mapped; 0 unmapped.
- 41 active Markdown files passed authority/link validation.
- 29 focused authority/public API/reference tests passed with one Pydantic
  deprecation warning.

No service, database, or browser stack was started for this slice.

## Next Step

No implementation plan is active. Choose the next feature from the coverage
matrix and run only its owning focused validation. If authenticated/multi-session
selection becomes the next feature, design the consumer-owned authorization
resolver before changing FastAPI or runtime contracts.
