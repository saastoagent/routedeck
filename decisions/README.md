# Decisions

Architectural decision records live here.

Create an ADR when a decision changes future implementation, ownership,
interfaces, migration strategy, validation strategy, or product/framework
boundaries.

- [ADR-001: RouteDeck Is A LangGraph-Native Dynamic UI Application Framework](./ADR-001-langgraph-native-routedeck.md)
- [ADR-002: RouteDeck Supports Two Adoption Modes Through One Kernel](./ADR-002-two-adoption-modes-one-kernel.md)
- [ADR-003: RouteDeck Governs Agentic Interaction State](./ADR-003-agentic-interaction-state-governor.md)
- [ADR-004: RouteDeck And Medusa Advance Through Consumer-Driven Runtime Slices](./ADR-004-routedeck-medusa-consumer-driven-runtime.md)
- [ADR-005: RouteDeck Uses Named State Actions And Operation-Centric Consumers](./ADR-005-operation-centric-state-and-consumer-structure.md)

ADR-005 is the current structural implementation decision. It preserves the
ADR-004 product/framework boundary and buyer behavior while replacing reducer
APIs, standardizing event identifiers, making SQLAlchemy persistence portable,
and fixing the Medusa and Navgraph module boundaries.

ADR-004 remains the controlling scope and migration decision. It
links the approved
[RouteDeck and Medusa buyer-agent design](../docs/superpowers/specs/2026-07-11-routedeck-medusa-agent-design.md)
to its active
[implementation plan](../docs/superpowers/plans/2026-07-11-routedeck-medusa-agent-implementation.md)
and fixes execution to the local Windows development machine.

ADR-003 remains historical rationale for RouteDeck's interaction-governance
identity and host-executor boundary. ADR-001 and ADR-002 are also retained as
history where later decisions supersede their release sequencing and scope.
