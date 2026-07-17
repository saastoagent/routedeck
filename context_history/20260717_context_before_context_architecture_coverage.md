# RouteDeck Context

Last updated: 2026-07-14
Status: the standalone RouteDeck framework and Medusa buyer agent are in
architecture-cleanup closeout. Execution is local Windows only.

## Start Here

1. [Critical prompt](./critical_prompt.md)
2. [ADR-004: RouteDeck And Medusa Advance Through Consumer-Driven Runtime Slices](./decisions/ADR-004-routedeck-medusa-consumer-driven-runtime.md)
3. [Approved RouteDeck and Medusa buyer-agent design](./docs/superpowers/specs/2026-07-11-routedeck-medusa-agent-design.md)
4. [Active architecture-cleanup plan](./docs/superpowers/plans/2026-07-14-routedeck-architecture-cleanup.md)
5. [Current context](./context.md)
6. [Decision index](./decisions/README.md)
7. [RouteDeck reference](./docs/route-deck-reference.md) for existing feature vocabulary and payloads,
   subject to ADR-004 and the approved design where older target language conflicts
8. [Architecture code map](./architecture/code-map.md)
9. [Test index](./test_index/README.md)
10. [Approved RouteDeck and Medusa implementation plan](./docs/superpowers/plans/2026-07-11-routedeck-medusa-agent-implementation.md) for completed slice history

Do not resume the
[retired full-stack refactor plan](./docs/superpowers/plans/2026-07-10-routedeck-full-stack-framework-refactor.md).
It is retained as historical material only.

## Active Implementation Authority

The authority chain is ADR-004 -> ADR-005 -> approved design -> active cleanup
plan. ADR-003 remains historical rationale for RouteDeck's product identity and
tool-supervision boundary.

## Locked Product Direction

RouteDeck is state management and interaction governance for agentic
applications.

Its job is to keep the agent grounded in the current application state:

- give the agent only the context it currently needs
- expose only currently legal tools/operations
- preserve product identity grounding through scoped opaque handles
- reject fabricated, stale, hidden, or ineligible handles before private ID
  resolution
- apply product-supplied guards and review requirements
- manage navgraph location, navigation history, active surfaces, selections,
  feedback, and relevant tool-result context
- keep backend interaction state, SSE updates, and frontend projection aligned

The navgraph is the application's interaction map, not the agent's execution
graph. It describes user-facing states, transitions, tools, surfaces, deep
links, and recovery behavior.

## Tool Supervision Boundary

Every application-semantic read or write tool call must cross RouteDeck before
execution.

```text
agent proposes tool call
  -> RouteDeck allows, blocks, requests input, or requires review
  -> host agent runtime invokes the product tool only when allowed
  -> host reports result/failure to RouteDeck
  -> RouteDeck updates interaction/session state, context, surfaces, and events
```

RouteDeck does not call the tool. It oversees the call and returns structured
feedback. The host application owns the agent runtime, product tools, domain
records, authentication system, prompts, model calls, and side effects.

## Identifier Rule

Medusa is authoritative for real product, variant, cart, line-item, shipping,
payment-provider, and order IDs. RouteDeck stores those IDs only in classified
private entity bindings and exposes scoped opaque handles in public projections,
model context, URLs, and surface props. At execution, RouteDeck resolves an
opaque handle only when its private binding is currently allowlisted for the
operation, entity kind, node, and session version. The Medusa handler receives
the resolved private ID; neither the browser nor the model does.

## Medusa Is The First Consumer

The standalone Medusa guest-buyer agent now drives RouteDeck development
through consumer-driven vertical slices. Each slice introduces only the
framework capability immediately consumed by matching Medusa behavior. A
RouteDeck-only result never completes a slice; the corresponding Medusa backend
and browser behavior must also work at the plan's required gates.

The Medusa application owns Store API access, commerce models, providers,
guards, handlers, LangGraph prompt/model behavior, and product surfaces.
RouteDeck owns product-neutral feature composition, interaction/session state,
supervision, persistence, transport, and frontend synchronization. Product
handlers execute only through the injected host executor.

Corpus remains an existing integration and useful historical behavior
reference, but it no longer controls implementation sequencing. Preserve the
Medusa **2026-06-10 gap audit** and its **chat-to-projection convergence** rule
as acceptance evidence for the standalone buyer agent.

## Current Implementation Reality

- `ApplicationSpec`/`FeatureSpec` compile into one immutable application and
  frontend contract; `FeatureBindings.merge(...)` composes feature-owned
  implementations and rejects duplicate ownership.
- One canonical session aggregate and `RouteDeckOperationRunner` govern
  navigation, providers, guards, reviews, effects, events, and projections.
- SQLAlchemy provides SQLite and PostgreSQL persistence behind the same store
  contract; FastAPI provides generic HTTP, private forms, and public SSE.
- LangGraph middleware injects active RouteDeck context/policies and exposes
  structured runner-owned tools without owning product topology.
- `packages/core` and `packages/react` provide the headless store and React
  primitives, including dynamic surfaces, history, review, forms, and Navgraph.
- The Medusa consumer owns all Store API transport and commerce logic in
  operation-centric features. Its chat-driven and surface-driven paths converge
  on the same runner.
- Model roles are explicit, and the live product path has no canned response,
  phrase router, substitute data source, or hidden execution path.

The remaining work in the active plan is focused verification, live buyer-flow
proof, diff review, and the requested RouteDeck-only commit.

## Approved Runtime Scope

ADR-004 authorizes feature-composed authoring, durable RouteDeck session and
event state, generic FastAPI/SSE and SQLAlchemy SQLite/PostgreSQL adapters, optional LangGraph
middleware, headless/React packages, and the standalone Medusa buyer-agent
portability proof.

RouteDeck still does not own product tool execution or Medusa business logic.
The product supplies an injected executor, real Store API data, and explicit
handlers/providers/guards. Missing data, credentials, dependencies, or
invariants fail visibly; product paths do not substitute fixtures, canned
responses, heuristic routing, or silent fallbacks.

## Migration And Validation Rule

1. Write the focused failing framework or consumer test for the slice.
2. Add only the RouteDeck capability immediately consumed by Medusa.
3. Route both agent and UI operations through the same supervised runner.
4. Prove the matching Medusa backend and browser behavior against real local
   sources of truth at the plan's required integration gates.
5. Delete superseded or duplicate paths after replacement and boundary proof.

Implementation, databases, services, test stacks, browser automation, and
release verification run on the local Windows development machine. Do not
probe, select, or fall back to the Mac mini. Start services only in an active
plan task that expressly authorizes them, and report the exact command and
smoke URL.

## Historical Decisions

- `ADR-001-langgraph-native-routedeck.md`: historical rationale for not
  reinventing execution graphs; superseded for required LangGraph/compiler
  direction.
- `ADR-002-two-adoption-modes-one-kernel.md`: historical runtime-neutral ideas;
  superseded for first-release multi-mode/durability requirements.
- `ADR-003-agentic-interaction-state-governor.md`: historical rationale for
  interaction governance and host-owned product-tool execution; superseded by
  ADR-004 for sequencing and approved runtime scope.
- `docs/superpowers/plans/2026-07-10-routedeck-full-stack-framework-refactor.md`:
  retired and must not be executed.
