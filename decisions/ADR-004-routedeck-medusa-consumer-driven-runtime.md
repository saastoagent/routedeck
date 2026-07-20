# ADR-004: RouteDeck And Medusa Advance Through Consumer-Driven Runtime Slices

Status: Accepted
Date: 2026-07-11

ADR-004 preserves ADR-003's interaction-governance identity and supersedes its
Corpus-first sequencing and explicit deferrals. The approved Medusa buyer-agent
design authorizes feature-composed authoring, durable RouteDeck state, generic
FastAPI/SSE and SQLAlchemy SQLite/PostgreSQL adapters, optional LangGraph middleware, and the
standalone Medusa portability proof. Product handlers still execute through an
injected host executor; RouteDeck contains no Medusa business logic.

## Active Authority

The complete requirements and boundaries live in the approved
[RouteDeck and Medusa buyer-agent design](../docs/archive/superpowers/specs/2026-07-11-routedeck-medusa-agent-design.md).
Its executable sequence is the
[RouteDeck and Medusa buyer-agent implementation plan](../docs/archive/superpowers/plans/2026-07-11-routedeck-medusa-agent-implementation.md).

Implementation, services, test stacks, browser automation, and release
verification run locally on the Windows development machine. The Mac mini is
outside the active runtime decision unless the user makes a later explicit
change.

ADR-003 remains historical rationale for RouteDeck's interaction-governance
identity and injected product-tool execution boundary. Where its sequencing or
scope conflicts with the approved design, ADR-004 controls.

## Implementation Status (Verified 2026-07-20)

This status records how the accepted decision is realized; it does not add a
new architectural choice.

- The standalone Medusa consumer owns the typed Store client, catalog, cart,
  checkout, order placement/reconciliation, product graphs/models/prompts,
  market/session initialization, product UI, and protected local stack.
- The product host explicitly chooses guest-cookie session policy, browser
  origins, worker/instance values, review/resume TTLs, and local cookie
  security. RouteDeck does not choose those deployment values.
- Checkout and order code share one Medusa-owned contact identity function, and
  backend schemas plus frontend decoders use one Medusa-owned parity-vector
  contract. Neither concern moved into RouteDeck.
- The browser reaches Medusa commerce only through supervised RouteDeck
  operations; it has no direct `/store/*` transport path.

The complete implementation-to-contract-to-proof crosswalk is retained in
[`knowledgebase/runtime-boundary-implementation-coverage.md`](../knowledgebase/runtime-boundary-implementation-coverage.md).
