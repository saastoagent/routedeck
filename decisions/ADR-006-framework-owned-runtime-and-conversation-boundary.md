# ADR-006: RouteDeck Owns Runtime Assembly And The Generic Conversation Boundary

Status: Accepted
Date: 2026-07-15

ADR-006 partially supersedes ADR-005. The superseded clause is the statement
that Medusa's `runtime_factory.py` assembles RouteDeck runtime infrastructure.
That statement remains in ADR-005 as a record of the structure accepted on
2026-07-12, but it is no longer the controlling ownership boundary. All other
ADR-005 decisions remain accepted.

## Context

ADR-005 made the state APIs and consumer structure clearer, but it still put
generic RouteDeck construction inside the Medusa consumer. Medusa also retained
generic control flow for starting an assistant-authored turn and presenting the
result. Those responsibilities use RouteDeck contracts, leases, persistence,
supervision, and failure semantics; they are framework behavior rather than
commerce behavior.

A product composition root must choose and configure framework adapters, but
that does not make the adapters' assembly or lifecycle product-owned. Leaving
that machinery in Medusa would make every consumer rebuild the same runtime and
conversation boundary and would prevent Medusa from being a business-logic-only
reference consumer.

## Decision

RouteDeck owns the reusable runtime and conversation control flow.

The framework owns:

- assembly of the generic runtime, including persistence resources, codecs,
  lifecycle, runtime services, operation and navigation runners, projection,
  notification, and the configured agent-driver boundary
- the generic conversation driver for user-authored and assistant-initiated
  turns, including turn acquisition, agent invocation, typed stream handling,
  review handoff, completion, interruption, persistence, and explicit failure
  reporting
- typed assistant-initiation and assistant-presentation contracts, including
  the public conversation events and state needed by transports and framework
  clients to present an assistant turn consistently
- framework adapter composition for RouteDeck core, SQLAlchemy, LangGraph,
  FastAPI/SSE, and React conversation state

Medusa owns only product responsibilities:

- commerce logic, operation handlers, product declarations, and bindings
- product configuration and secrets
- product-owned agent graphs, prompts, models, and model selection
- the typed Medusa Store client and all Medusa API behavior
- product readiness checks and market/configuration validation
- product UI components, layout, visual design, copy, and rendering of
  RouteDeck's typed presentation state

Medusa supplies those product implementations and configuration through typed
RouteDeck ports. A Medusa entry point may call a public RouteDeck factory, but a
Medusa-owned `runtime_factory.py` must not construct RouteDeck runners,
navigation, persistence resources, conversation leases, or generic assistant
presentation machinery.

Typed assistant initiation does not transfer product authorship to RouteDeck.
RouteDeck owns the trigger, lifecycle, validation, persistence, and presentation
shape; Medusa owns the graph, prompt, model, and resulting product wording.
Likewise, RouteDeck owns typed client synchronization while Medusa owns the UI
that renders it.

This decision does not move commerce rules, Store calls, product graphs, model
selection, or product tool side effects into RouteDeck. It preserves the
ADR-003 and ADR-004 product/framework boundary: RouteDeck governs interaction
state and reusable execution lifecycle while product implementations remain the
authority for product behavior.

Required dependencies fail explicitly. RouteDeck does not replace a missing
product graph, model, Store client, or readiness result with a canned assistant
message, alternate provider, or synthetic product response.

## Consequences

- Consumers configure one RouteDeck runtime instead of rebuilding framework
  infrastructure in product packages.
- User-authored and assistant-initiated turns share one typed lifecycle and one
  failure model.
- Assistant conversation state and presentation remain portable across
  transports and clients without dictating product visuals or wording.
- Medusa becomes a stricter reference consumer: its backend contains product
  behavior and typed bindings, not reusable RouteDeck control flow.
- Framework adapters remain optional and explicitly selected; RouteDeck core
  does not acquire Medusa or mandatory LangGraph dependencies.
- Boundary verification can reject Medusa imports or construction of generic
  runtime, conversation, and presentation infrastructure.

## Implementation Status (Verified 2026-07-20)

This status records realization of the accepted ownership decision; it does not
change the decision.

- `build_routedeck_runtime(...)` constructs the one runner, navigation over
  that runner, projection, lifecycle, and optional product-supplied driver.
- `create_routedeck_router_from_runtime_provider(...)` derives one generic
  FastAPI plane from that runtime and requires a host-supplied
  `RouteDeckSessionSelector`. `GuestCookieSessionSelector` is an explicit guest
  adapter, not a hidden framework default.
- `runAssistantInitiatedTurn(...)` in `@routedeck/core` owns assistant-only
  stream validation, durable completion proof, version convergence, conflict
  reload, and canonical conversation reload. Medusa supplies greeting policy,
  request identity, and buyer-facing copy.
- Generic framework packages contain product-neutral production copy. The
  schema-4 boundary report rejects product vocabulary, product-owned assistant
  stream state machines, duplicate runtime construction, direct Store browser
  calls, and product-owned LangGraph driving.

The implementation-to-contract-to-proof crosswalk is
[`knowledgebase/runtime-boundary-implementation-coverage.md`](../knowledgebase/runtime-boundary-implementation-coverage.md).

## Authority Chain

ADR-006 is the controlling decision for runtime assembly, generic conversation
driving, and typed assistant initiation/presentation. ADR-005 remains the
controlling structural decision for named state actions, SQLAlchemy repository
portability, canonical event identifiers, operation-centric product slices,
modular RouteDeck orchestration, and Navgraph behavior. ADR-004 continues to
control scope, migration, and local execution. ADR-003 remains the historical
rationale for interaction governance and the product-tool boundary.
