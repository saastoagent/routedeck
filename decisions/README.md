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
- [ADR-006: RouteDeck Owns Runtime Assembly And The Generic Conversation Boundary](./ADR-006-framework-owned-runtime-and-conversation-boundary.md)

ADR-006 is the current authority for runtime assembly, generic conversation
driving, and typed assistant initiation/presentation. RouteDeck owns that
reusable infrastructure; Medusa owns only product logic, configuration, graphs,
prompts, models, its Store client, readiness, and UI. ADR-006 partially
supersedes the ADR-005 clause that assigned RouteDeck infrastructure assembly to
Medusa's `runtime_factory.py`.

The completed implementation record is archived in the
[runtime-boundary refactor plan](../docs/archive/superpowers/plans/2026-07-15-routedeck-runtime-boundary-refactor.md).
Archived plans remain historical and do not override ADR-006.

ADR-005 remains the structural implementation authority for named state
actions, canonical event identifiers, SQLAlchemy repository portability,
operation-centric product slices, modular RouteDeck orchestration, and Navgraph
behavior. Its superseded runtime-assembly clause is retained as historical
record.

ADR-004 remains the controlling scope and local-execution decision. It links
the approved
[RouteDeck and Medusa buyer-agent design](../docs/archive/superpowers/specs/2026-07-11-routedeck-medusa-agent-design.md)
to its completed historical
[implementation plan](../docs/archive/superpowers/plans/2026-07-11-routedeck-medusa-agent-implementation.md)
and fixes execution to the local Windows development machine.

ADR-003 remains historical rationale for RouteDeck's interaction-governance
identity and host-executor boundary. ADR-001 and ADR-002 are also retained as
history where later decisions supersede their release sequencing and scope.
