# ADR-002: RouteDeck Supports Two Adoption Modes Through One Kernel

Status: Accepted
Date: 2026-07-10

## Context

RouteDeck is intended to become the default framework for building robust
agentic applications. Two developer groups need it:

1. ordinary developers and agent-assisted or vibe coders who want a predictable
   full-stack path with guardrails, stable typed operations, surfaces, streaming,
   and frontend state already assembled; and
2. advanced agent developers who already have a working agent or custom graph
   but need RouteDeck's state management, interaction management, review,
   projections, events, surfaces, diagnostics, and frontend store.

Building separate runtimes for these groups would duplicate the most important
RouteDeck semantics and create incompatible products.

## Decision

RouteDeck will provide two adoption modes over one product-neutral kernel.

The RouteDeck application specification is the single interaction source of
truth for public nodes, flows, operations, guards, surface identity and
placement, affordances, and declared event types. Product providers may resolve
dynamic context and surface props, but they do not redefine those contracts in
parallel catalogs.

### RouteDeck Full Flow

This is the default and recommended path. A product imports RouteDeck and
declares domain state, user-facing nodes and flows, operations, guards, handlers,
context providers, and surfaces. RouteDeck validates and compiles that
application definition into a LangGraph-backed backend runtime plus the typed
event, SSE, projection, diagnostics, and React-store integration.

### RouteDeck Core Integration

This path is for an existing agent or custom graph. The developer retains their
execution topology and domain behavior behind a typed executor adapter. The
adapter maps snapshots, dispatches, execution results, and streamed execution
events into the same RouteDeck runtime used by Full Flow.

Custom LangGraph graphs are the first production-supported integration target.
The executor protocol remains product-neutral so future adapters can support
other agent runtimes without changing RouteDeck's interaction contracts.

## Shared Kernel

Both modes use the same:

- manifest/application specification
- operation and readiness models
- guard, review, and recovery semantics
- runtime state and projection
- server-authoritative sessions, optimistic version checks, idempotent dispatch,
  and explicit interrupted-operation recovery
- a coordinated persistence boundary that atomically commits public state,
  idempotent results, projection/terminal events, and an event outbox
- surface and affordance contracts
- navigation and deeplink contracts
- typed event envelope, sequencing, and visibility rules
- SSE transport and replay semantics
- React store, hooks, surface host, and diagnostics
- conformance and contract tests

Full Flow is the shared kernel plus the RouteDeck LangGraph compiler. Core
Integration is the shared kernel plus a developer-provided executor adapter.

## Event Architecture

RouteDeck owns one event architecture with explicit semantic channels such as
`assistant`, `runtime`, `tool`, `surface`, and `diagnostic`. Events share IDs,
run/turn correlation, sequence numbers, projection versions, timestamps, and a
typed payload contract. Standard events use framework payload schemas; custom
events declare a payload model in the application specification before they can
be emitted or persisted.

Products may expose filtered SSE endpoints or a multiplexed endpoint. Separate
channels must not collapse visibility boundaries: public assistant consumers do
not receive private diagnostics, raw graph state, credentials, or hidden route
operations.

## Example Requirement

RouteDeck readiness requires two self-contained examples independent of Corpus:

1. a Full Flow example in which RouteDeck compiles and runs a small real
   LangGraph-backed agentic application with SSE and React surfaces; and
2. a Core Integration example in which an existing/custom agent is adapted to
   RouteDeck interaction state, typed events, projections, and React state
   without rewriting its execution topology.

Each example must have its own README, backend tests, frontend tests, smoke
command, and fail-loud behavior when a real required dependency is unavailable.
Fixtures may be used only inside tests.

## Consequences

- Corpus becomes a consuming application definition rather than a framework
  runtime implementation.
- Generic projection, navigation, review, event sequencing, SSE formatting, and
  frontend state mechanics move out of Corpus.
- RouteDeck's main backend direction remains LangGraph-native.
- RouteDeck atomically claims a dispatch before invoking an executor and never
  silently reruns an interrupted external side effect. Product handlers receive
  the dispatch idempotency key for downstream APIs; RouteDeck does not claim
  impossible exactly-once guarantees across external systems.
- The golden path includes a durable SQLite reference backend for single-host
  apps. Distributed backends implement the same coordinated protocol rather
  than composing unrelated stores without an atomic commit boundary.
- Framework-neutral protocols remain free of product literals and unnecessary
  LangGraph implementation types.
- A feature is not complete until it behaves consistently in both adoption
  modes or is explicitly documented as Full-Flow-only compiler behavior.
