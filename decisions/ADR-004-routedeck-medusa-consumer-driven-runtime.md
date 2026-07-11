# ADR-004: RouteDeck And Medusa Advance Through Consumer-Driven Runtime Slices

Status: Accepted
Date: 2026-07-11

ADR-004 preserves ADR-003's interaction-governance identity and supersedes its
Corpus-first sequencing and explicit deferrals. The approved Medusa buyer-agent
design authorizes feature-composed authoring, durable RouteDeck state, generic
FastAPI/SSE and SQLite adapters, optional LangGraph middleware, and the
standalone Medusa portability proof. Product handlers still execute through an
injected host executor; RouteDeck contains no Medusa business logic.

## Active Authority

The complete requirements and boundaries live in the approved
[RouteDeck and Medusa buyer-agent design](../docs/superpowers/specs/2026-07-11-routedeck-medusa-agent-design.md).
Its executable sequence is the
[RouteDeck and Medusa buyer-agent implementation plan](../docs/superpowers/plans/2026-07-11-routedeck-medusa-agent-implementation.md).

Implementation, services, test stacks, browser automation, and release
verification run locally on the Windows development machine. The Mac mini is
outside the active runtime decision unless the user makes a later explicit
change.

ADR-003 remains historical rationale for RouteDeck's interaction-governance
identity and injected product-tool execution boundary. Where its sequencing or
scope conflicts with the approved design, ADR-004 controls.
