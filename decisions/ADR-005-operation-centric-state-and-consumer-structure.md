# ADR-005: RouteDeck Uses Named State Actions And Operation-Centric Consumers

Status: Accepted; runtime-assembly clause partially superseded by ADR-006
Date: 2026-07-12

## Supersession Note

ADR-006 partially supersedes only the Decision clause stating that Medusa's
`runtime_factory.py` assembles RouteDeck runtime infrastructure. That clause is
preserved below as a historical record of the structure accepted on
2026-07-12, but it is no longer the controlling ownership boundary. RouteDeck
now owns generic runtime assembly, generic conversation driving, and typed
assistant initiation/presentation. All other decisions in this ADR remain
accepted.

## Context

The first Medusa buyer flow proved the RouteDeck boundaries, but its reducer
APIs and broad composition/handler modules made ordinary feature work harder to
read and extend. SQLite-specific persistence also constrained a future database
change, and the always-visible inspector compressed the buyer workspace.

The buyer behavior and the ADR-004 framework/product boundary remain correct.
This decision changes the internal developer model without changing the public
buyer journey.

## Decision

- Backend state transitions are named methods on
  `RouteDeckSessionAggregate`. The immutable `RouteDeckSession` remains the one
  canonical authority; callers do not submit arbitrary reducer events.
- Frontend state is owned by `RouteDeckObservableState` and changed through
  named store actions. React bindings observe that store instead of duplicating
  state logic.
- Durable storage uses SQLAlchemy ORM repositories behind one store contract.
  SQLite and PostgreSQL URLs are supported explicitly; product code does not
  contain raw persistence SQL or select a silent fallback database.
- Public event identifiers use the canonical `RouteDeckEventType` name and have
  no alternate exported identifier.
- Medusa remains a thin consumer. `composition.py` declares the app,
  `bindings.py` wires typed product implementations, and `runtime_factory.py`
  assembles RouteDeck runtime infrastructure. Complex commerce mutations are
  organized as operation-centric vertical slices, with shared helpers kept
  explicit and side-effect-free.
- RouteDeck's own orchestration is modular by lifecycle responsibility:
  runtime projection builders are separate from the extensible runtime base;
  FastAPI request/session/private-form/response/inspection services are
  separate from endpoint registration; and supervision composes explicit
  runner, review, outcome, recovery, and result slices behind the single
  `RouteDeckOperationRunner` interface.
- The RouteDeck Navgraph is a collapsible product-neutral sidebar. Opening it
  shows the complete compiled sitemap and all transitions in a large overlay;
  fullscreen is available for inspection. Graph selection is read-only and
  cannot dispatch product operations or navigate the buyer.

## Consequences

- Framework callers use intention-revealing actions while state invariants stay
  centralized.
- A persistence-layer change is configuration plus adapter work, not a rewrite
  of product business logic.
- Medusa operation modules can be investigated independently without hiding API
  calls or commerce rules in RouteDeck.
- The surface-driven and chat-driven paths still converge on the same
  `RouteDeckOperationRunner`, so the buyer-visible flow and review semantics do
  not diverge.
- No reducer or alternate event-name shim is retained.

## Verification Boundary

Focused verification must cover aggregate actions, one SQLite repository path,
the explicit PostgreSQL dialect path, chat/tool dispatch, real Medusa checkout,
the React shell, the complete Navgraph, and the production frontend build. A
large undifferentiated test count is not a substitute for those product gates.
