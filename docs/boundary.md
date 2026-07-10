# RouteDeck Boundary

Status: Target boundary accepted; implementation is transitional
Date: 2026-07-10

For the full reference and developer guide, read
[`route-deck-reference.md`](./route-deck-reference.md) and
[`using-routedeck.md`](./using-routedeck.md).

RouteDeck owns the product-neutral mechanics required to turn product behavior
into a robust full-stack agentic application.

It owns:

- application, node, flow, operation, guard, review, and surface contracts
- the first-class LangGraph Full Flow compiler
- the executor boundary for existing/custom agents
- server-authoritative sessions, versions, dispatch claims, and idempotency
- navigation, projection, recovery, and interaction-state mechanics
- typed event schemas, channels, visibility, ordering, persistence, and replay
- FastAPI/SSE framing and product-neutral transport factories
- the React event/store/surface runtime and diagnostics/debugger primitives
- conformance tests and standalone examples for both adoption modes

Consuming products own:

- domain state fields and private execution facts
- prompts, model/provider selection, and assistant meaning
- auth, tenancy, workspace, account, and persistence policy
- database queries, domain handlers, external APIs, and side effects
- product guards and context facts supplied through RouteDeck protocols
- dynamic surface props, React surface components, layout, copy, and identity

The RouteDeck application specification is the single source for public nodes,
flows, operations, surface identity/placement, affordances, and declared event
schemas. Product providers resolve live values; they do not redefine those
contracts in a second catalog.

`routedeck_core` stays product-neutral. `routedeck_langgraph` is first-class,
not optional in the Full Flow architecture, while its executor protocol keeps
the core free of unnecessary LangGraph implementation types.

For SaaStoAgent, Corpus must become a thin Full Flow application definition plus
domain behavior. Corpus may extend RouteDeck contracts only for genuine product
fields. It must not own generic runtime subclasses, projection assembly,
navigation stacks, review mechanics, event sequencing, SSE formatting, or
client-authoritative graph-state reconstruction.

The older `backend/services/route_deck/` SaaStoAgent adapter/catalog is product
compatibility code, not RouteDeck framework ownership. It must be explicitly
migrated, retained as a named compatibility boundary, or retired after call-site
proof.
