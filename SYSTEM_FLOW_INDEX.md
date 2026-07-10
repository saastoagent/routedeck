# System Flow Index - RouteDeck

Last updated: 2026-07-10
Status: Target flow accepted; implementation is transitional

This is the compact source of truth for intended runtime and UX flows. Use
`context.md` for the current implementation snapshot and
`architecture/components/` for subsystem detail.

## Framework Spine

```text
Product RouteDeck application specification
  -> compile-time contract validation
  -> Full Flow LangGraph executor OR existing-agent executor adapter
  -> shared RouteDeck interaction kernel
  -> server-authoritative session and guarded/reviewed dispatch
  -> declared outcome and state commit
  -> projection and active surfaces
  -> ordered typed event log
  -> filtered/multiplexed SSE channel views
  -> RouteDeck React store, product surfaces, assistant, and diagnostics
```

The application specification is the single source for public nodes, flows,
operations, surface identity/placement, affordances, and event schemas. Private
execution topology and domain state remain behind the executor/product boundary.

## Adoption Flows

### Full Flow

```text
product declarations and domain handlers
  -> RouteDeck Full Flow compiler
  -> LangGraph-backed RouteDeck executor
  -> shared kernel and full-stack transport/store path
```

### Core Integration

```text
unchanged existing/custom agent
  -> typed RouteDeck executor adapter
  -> shared kernel and full-stack transport/store path
```

Both flows must pass the same runtime, event, projection, guard, review, surface,
and React conformance assertions.

## Dispatch Flow

```text
session id + expected projection version + idempotency key + typed intent
  -> load authoritative session
  -> validate operation/input/auth/guard/review policy
  -> atomically claim dispatch
  -> invoke executor once with correlation/idempotency context
  -> validate declared outcome and public node
  -> commit authoritative state and projection
  -> persist ordered terminal events
  -> return/replay the recorded result
```

Rules:

- Clients never submit authoritative graph state.
- Duplicate dispatch keys never invoke the executor twice.
- Interrupted external work is explicit; RouteDeck does not silently rerun it.
- Product handlers propagate the idempotency key to downstream side effects.
- A blocked guard or staged review never reaches the executor.

## Event And SSE Flow

```text
runtime, executor, assistant, tool, or surface emission
  -> validate event type, payload schema, channel, and visibility
  -> allocate session-scoped sequence
  -> persist before fan-out
  -> assistant | runtime | tool | surface | diagnostic channel view
  -> SSE id/event/data frame and replay after Last-Event-ID
  -> client dedupe/order/stale-projection reduction
```

Diagnostic and hidden execution data never leak into public assistant or runtime
views. Network close without a terminal semantic event is interrupted, not
successful.

## Surface Flow

```text
declared surface identity and node placement
  -> product provider resolves dynamic props only
  -> projection selects legal active surface
  -> React component registry renders product component
  -> typed affordance intent returns through shared dispatch
```

The frontend registry maps component keys to React components; it does not
duplicate node, flow, operation, or surface policy.

## Current Compatibility Debt

- `RouteDeckApp.compile()` does not yet build the target compiler/runtime.
- Existing dispatch still permits client-provided graph state in legacy paths.
- The shared typed event backend and `routedeck_fastapi` package do not yet
  exist.
- `routedeck_langgraph` currently provides validation/common wiring, not the
  complete Full Flow compiler or existing-agent executor.
- Corpus still owns generic runtime/event/projection mechanics pending vertical
  migration.

## Authorities And Validation

- Reference: `docs/route-deck-reference.md`
- Decisions: `decisions/ADR-001-langgraph-native-routedeck.md` and
  `decisions/ADR-002-two-adoption-modes-one-kernel.md`
- Plan: `docs/superpowers/plans/2026-07-10-routedeck-full-stack-framework-refactor.md`
- Ownership: `architecture/code-map.md`
- Validation commands and meaning: `test_index/README.md`
