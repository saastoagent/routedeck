# RouteDeck Framework Architecture

Status: Target architecture accepted; implementation is transitional
Date: 2026-07-10

Read [`route-deck-reference.md`](./route-deck-reference.md),
[`agentic-ui-state-runtime.md`](./agentic-ui-state-runtime.md),
[`ADR-001`](../decisions/ADR-001-langgraph-native-routedeck.md), and
[`ADR-002`](../decisions/ADR-002-two-adoption-modes-one-kernel.md) as the
authorities for framework meaning.

RouteDeck is a full-stack framework for robust agentic applications. It sits on
top of LangGraph for its first-class Python execution path and provides the
shared state, interaction, guard, review, projection, surface, event/SSE,
diagnostic, and React-store mechanics around product behavior.

## One Kernel, Two Adoption Modes

### Full Flow

A product declares its domain state, public interaction nodes and flows,
operations, guards, handlers, context providers, surfaces, and event schemas.
RouteDeck validates the declaration and compiles the LangGraph-backed runtime,
FastAPI/SSE contract, projection path, and React-facing state contract.

Product code should not construct LangGraph plumbing, runtime subclasses,
projection builders, generic event buses, or SSE frames in this mode.

### Core Integration

An advanced developer keeps an existing agent or compiled LangGraph graph. A
typed executor adapter maps that execution into the same RouteDeck interaction
kernel without forcing public interaction nodes to match private execution
nodes or requiring the graph to be rewritten.

Only executor construction differs. Operation legality, versioning,
idempotency, guards, review, surfaces, projections, events, diagnostics, and
React behavior remain shared and must pass one conformance suite.

## Single Interaction Source Of Truth

The RouteDeck application specification owns the public interaction contract:

- nodes and declared flow outcomes
- operations, inputs, guards, and review policy
- surface identity, placement, variants, and affordances
- public event types and payload schemas

Product context and surface providers may resolve live facts and dynamic props.
They must not repeat identity or routing truth in parallel catalogs. An existing
agent may retain a richer private execution topology behind its adapter.

## Package Responsibilities

### `routedeck_core`

Product-neutral application schemas and the interaction kernel:

- server-authoritative session and projection state
- atomic dispatch claims, expected-version checks, and idempotency records
- operation validation, guard evaluation, review, and recovery
- flow outcome validation, navigation, projection, and surfaces
- typed event envelopes, payload schemas, visibility, ordering, and replay
- executor, session-store, event-backend, and context-provider protocols

It must not import SaaStoAgent/Corpus, Medusa, product models, or product
handlers. Framework-neutral interfaces must not expose unnecessary LangGraph
types.

### `routedeck_langgraph`

The first-class Python execution implementation:

- Full Flow compiler from a RouteDeck application specification
- executor adapter for existing/custom compiled LangGraph graphs
- mapping between private execution nodes and public interaction outcomes
- LangGraph callback/tool/assistant events mapped into typed RouteDeck events

### `routedeck_fastapi` (planned)

Product-neutral HTTP and SSE transport:

- session, turn, dispatch, review, snapshot, and inspect routes
- filtered and multiplexed event-channel endpoints
- SSE IDs, replay cursors, keepalive, bounded subscriptions, and disconnect
  cleanup
- caller-supplied product and diagnostic authentication dependencies

### `@routedeck/react`

The frontend state and surface runtime:

- typed event client and reducer
- ordering, deduplication, reconnect, and stale-projection rejection
- server-authoritative dispatch/navigation behavior
- surface component registry and visible missing-component errors
- hooks, diagnostics, and debugger/authoring UI

Product shells still own layout, auth, visual identity, product copy, and actual
surface components.

## Reliability Boundary

RouteDeck atomically claims a dispatch before invoking the executor. Duplicate
idempotency keys cannot invoke it twice. A crash around an external side effect
is represented as interrupted work and is never silently retried as success.
Product handlers receive the idempotency key for downstream APIs because no
framework can promise exactly-once behavior across an uncoordinated external
system.

## Current Implementation Reality

The repository currently contains substantial core contracts,
`RouteDeckRuntimeBase`, a builder foundation, LangGraph validation/common graph
wiring, and the React store/debugger. It does not yet contain the complete
server-authoritative kernel, Full Flow compiler, existing-agent executor,
FastAPI/SSE package, or standalone two-mode examples described above.

The implementation sequence is defined in
[`2026-07-10-routedeck-full-stack-framework-refactor.md`](./superpowers/plans/2026-07-10-routedeck-full-stack-framework-refactor.md).
