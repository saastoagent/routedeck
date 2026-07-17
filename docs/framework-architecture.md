# RouteDeck Framework Architecture

Status: implemented reference architecture
Date: 2026-07-17

## Architecture In One Sentence

A product declares feature-owned interaction nodes and supplies real behavior;
RouteDeck compiles those declarations and runs one durable, supervised state
authority consumed by HTTP, agents, and React.

## Dependency Direction

```text
product declarations, bindings, callbacks, graph factory, components
                    |
                    v
routedeck_core <- routedeck_sqlalchemy
       ^        <- routedeck_fastapi
       ^        <- routedeck_langgraph
       |
generated frontend contract -> @routedeck/core -> @routedeck/react
```

Core imports no optional adapter or product. Optional adapters depend on core.
The product host composes them without reimplementing their algorithms.

## Python Packages

- `routedeck_core`: authoring contracts, compiler, canonical state, context,
  projection, navigation, supervision, ports, and runtime builder.
- `routedeck_sqlalchemy`: SQLite/PostgreSQL ORM store, fencing, journals,
  events, encryption, retention, recovery, and persistent runtime opener.
- `routedeck_fastapi`: one runtime-derived contract/session/operation/
  conversation/event/form/inspection plane.
- `routedeck_langgraph`: optional generic conversation driver, durable message
  reconstruction, model-context filtering, and supervised tools over
  product-owned graphs.
- `routedeck_testing`: explicitly test-only conformance helpers and models.

## Browser Packages

- `@routedeck/core`: generated contracts, strict decoding, HTTP/SSE and
  conversation clients, bootstrap/resync, exact request retention,
  routing/history, forms, and authoritative observable state.
- `@routedeck/react`: provider/hooks, named conversation presentation,
  surfaces, operations, forms, review, navigation, status/error, and read-only
  Navgraph primitives.
- `@routedeck/testing`: private frontend harnesses and factories.

## Authoring Model

Feature modules own complete nodes and outgoing transitions. The product
composition root selects features and one entry node. RouteDeck derives incoming
adjacency and compiles the one graph and frontend contract. Bindings remain
feature-owned and are validated for exact ownership.

## Runtime Narrow Waist

`RouteDeckRuntimeServices` holds the bound app, store, clock, notifier, ID
factory, one `RouteDeckOperationRunner`, navigation over that runner, and the
projector. `RouteDeckRuntime` adds sensitive codec, session callbacks, optional
agent driver, and lifecycle.

Every adapter derives from that runtime. There is no product-built runner,
second FastAPI dependency graph, second conversation driver, or browser state
authority.

## State And Reliability

- The server session is immutable, versioned, and canonical.
- Requests carry caller-owned identities and exact replay fingerprints.
- State, journals, results, and ordered public events commit atomically.
- Reviews are durable and revalidate current context.
- External outcome uncertainty is explicit and product-reconcilable.
- Private values remain encrypted and excluded from public projection/events.
- Browser state confirms only server projection; gaps trigger resync.

## Reference Consumer

`examples/medusa-agent` supplies catalog, cart, checkout, order, Store API,
prompt/model/graph, market, health, and buyer UI behavior. It consumes the
generic runtime without putting commerce behavior into RouteDeck.

See `architecture/feature-coverage.md` for complete feature-to-source-to-proof
coverage and `SYSTEM_FLOW_INDEX.md` for runtime sequences.
