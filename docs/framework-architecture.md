# RouteDeck Framework Architecture

Status: Implemented reference architecture
Date: 2026-07-12

Read [`route-deck-reference.md`](./route-deck-reference.md),
[`ADR-004`](../decisions/ADR-004-routedeck-medusa-consumer-driven-runtime.md),
and the approved
[buyer-agent design](./superpowers/specs/2026-07-11-routedeck-medusa-agent-design.md)
as the active authorities. `agentic-ui-state-runtime.md` and ADR-001 through
ADR-003 remain historical rationale where they do not conflict with ADR-004.

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

### `routedeck_fastapi`

Product-neutral HTTP and SSE transport:

- session, turn, dispatch, review, snapshot, and inspect routes
- durable, idempotent session creation and mutation replay
- filtered and multiplexed event-channel endpoints
- SSE IDs, replay cursors, keepalive, bounded subscriptions, and disconnect
  cleanup
- caller-supplied product and diagnostic authentication dependencies

### `@routedeck/react`

The frontend state and surface runtime:

- typed event client and observable store with named domain actions
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

Navigation, private-form saves, chat turns, and session creation also carry a
durable request identity. The SQLAlchemy adapter records the request fingerprint,
public-safe terminal result, committed session/projection versions, and event
cursor in the same transaction as canonical state. Replaying the exact request
returns that recorded result; reusing its ID with different input fails with
`request_id_reused`.

The browser retains an exact request ID and payload when delivery may have
succeeded but the response is unknown. It never invents a new ID or silently
replays a state-changing request. The caller must explicitly retry that exact
request or abandon it before issuing a conflicting payload.

## Current Implementation Reality

The repository implements the server-authoritative kernel and compiler,
LangGraph middleware/tool seam, generic FastAPI/SSE transport, fenced SQLAlchemy
persistence, generated TypeScript contracts, headless client store, React
primitives, and the standalone Medusa reference consumer. The Medusa app uses
Full Flow declarations while retaining a normal product-owned LangGraph agent.

The shipped SQLAlchemy adapter supports SQLite and PostgreSQL behind the same
ORM repository contract. It deliberately targets one fenced application
process. Multi-process or distributed deployments require an explicitly
designed worker policy with equivalent fencing and transaction semantics; they
are not emulated by an in-process fallback.
