# Critical Prompt - RouteDeck

RouteDeck is state management and interaction governance for agentic
applications. It gives an agent only the context it currently needs, supervises
every application-semantic operation, and keeps navigation, private bindings,
opaque handles, guards, surfaces, results, events, and browser state coherent.

RouteDeck is not the product agent, model, LangGraph topology, product tool
executor, product database, authentication system, or visual design system.

## Current Authority

1. [ADR-006](./decisions/ADR-006-framework-owned-runtime-and-conversation-boundary.md)
   controls runtime assembly and generic conversation ownership.
2. [ADR-005](./decisions/ADR-005-operation-centric-state-and-consumer-structure.md)
   controls non-superseded named-state and feature structure.
3. [ADR-004](./decisions/ADR-004-routedeck-medusa-consumer-driven-runtime.md)
   controls scope, the product/framework boundary, and local execution.
4. [RouteDeck reference](./docs/route-deck-reference.md) defines current
   framework contracts.
5. [Feature coverage](./architecture/feature-coverage.md), the
   [code map](./architecture/code-map.md), and component docs map those
   contracts to source and proof.

Completed plans, older designs, handoffs, context history, and reports are
historical evidence only. Their classification is defined in
`architecture/documentation-map.md`.

## North Star

```text
trusted product facts + feature-owned nodes
  -> RouteDeck compiles one immutable application/navgraph
  -> RouteDeck builds one durable runtime and scoped projection
  -> browser or agent proposes a declared operation
  -> RouteDeck allows, blocks, requests input, or requires review
  -> an allowed product handler executes through the host boundary
  -> the host reports a typed result/failure and delivery evidence
  -> RouteDeck commits state, events, surfaces, feedback, and client versions
```

The navgraph is the product's durable interaction map. It is not the product
agent's private model/tool execution graph.

## Ownership

RouteDeck owns reusable:

- `Application`/`Feature` compilation and complete graph validation;
- canonical session, conversation, operation, review, navigation, and surface
  state;
- one supervised operation runner and navigation over that exact runner;
- provider, guard, needs-input, review, effect, and recovery mechanics;
- operation-scoped context, private entity bindings, and opaque public handles;
- default-deny projection and model context;
- exact deep-link/history transactions and resume capabilities;
- durable request identity, replay/collision, leases, events, and persistence
  ports;
- framework runtime construction and lifecycle;
- generic FastAPI/SSE and optional LangGraph conversation integration;
- authoritative browser synchronization and product-neutral React primitives;
- read-only inspection and Navgraph diagnostics.

The consuming product owns:

- domain records, APIs, wire models, business validation, and side effects;
- authentication, users, tenants, session authorization, and deployment policy;
- feature declarations, implementations, product session initialization, and
  trusted facts;
- prompts, model selection, LangGraph topology, policy, personality, and copy;
- product components, props, affordance wording, and visual design;
- product recovery decisions and independent source-of-truth verification.

RouteDeck evaluates the declared boundary and coordinates execution. It never
becomes the commerce or product tool implementation.

## Declarative Authoring

Developers work feature-first:

1. A feature owns complete `Node` declarations.
2. Each node owns its available operations, providers, guards, surfaces,
   capabilities, route entry, and outgoing transitions.
3. A small composition root selects `Feature` objects and one entry node in an
   `Application`.
4. `compile_app(...)` derives incoming adjacency and validates the complete
   interaction graph.
5. `bind_app(...)` requires an exact implementation for every declared handler,
   provider, and guard.

Products do not maintain a second transition table or recreate generic
context, navigation, surface, feedback, event, or SSE behavior.

## Supervision And Identity

Every application-semantic read or write operation crosses
`RouteDeckOperationRunner`. The runner returns a typed disposition and only an
allowed invocation reaches the product handler.

Real entity IDs remain product-owned and server-private. Browser/model inputs
use opaque handles. Resolution succeeds only when the binding is currently
allowed for the session, operation, entity kind, node, and version. Fabricated,
stale, hidden, or cross-context handles fail before product execution.

External writes record delivery as `not_sent`, `possibly_sent`, or
`response_received`. An uncertain outcome becomes explicit recovery state; it
is never silently retried or reported as success.

## Runtime And Adapter Boundary

`build_routedeck_runtime(...)` constructs one runtime services container, one
runner, navigation over that runner, projection, and optional agent driver.
`open_sqlalchemy_routedeck_runtime(...)` opens explicit SQLite/PostgreSQL
resources and delegates assembly to the core builder.

The FastAPI adapter derives every generic route from one runtime. The optional
LangGraph adapter consumes product-supplied graphs, reconstructs durable
conversation, filters model context/tools, and routes tools through the one
runner. RouteDeck never compiles a product LangGraph topology.

## Session Selection Boundary

A RouteDeck session is one durable interaction context. RouteDeck owns the
selected session's state; the consumer owns users and authorization.

The Medusa reference currently selects one guest session through an HTTP-only
cookie. Separate browser profiles are isolated; tabs in one profile share that
guest session. An authenticated multi-session resolver is not implemented.
Future adapters must authorize a consumer-facing opaque handle before exposing
an internal `session_id` to RouteDeck persistence. They must not trust raw
browser-supplied internal IDs or fall back to a default session after denial.

## Non-Negotiable Rules

- LLM prose is not an application state change.
- UI affordances and agent tools use the same supervised operation path.
- Product facts come only from current projection/context or reported product
  tool results.
- Private IDs, credentials, private form values, diagnostics, and hidden
  operations never enter normal public/model context.
- Product surfaces and read-only Navgraph diagnostics remain separate.
- Navgraph selection never navigates, mutates state, or changes the URL.
- Route entry is structural and declared; no regex/phrase heuristic substitutes
  for product resolution.
- Internal `route.*` behavior is not rendered as ordinary product action chips.
- Legal operations are not rendered wholesale; surface, form, selector, review,
  hidden, and blocked posture is preserved.
- Assistant, interaction, tool/surface, and diagnostic events retain explicit
  semantics and visibility.
- No compatibility alias, duplicate runtime, alternate state authority, canned
  response, fixture data, heuristic router, or silent fallback may make a
  product path appear valid.
- Missing dependencies, data, bindings, guards, drivers, or invariants fail
  visibly.

## First Consumer

The standalone Medusa guest-buyer app is the reference consumer. Medusa owns
Store API transport, commerce truth, catalog/cart/checkout/order features,
market facts, prompts/models/graphs, and buyer UI. RouteDeck owns only the
product-neutral contracts and runtime listed above. The browser never calls
Medusa `/store/*` directly.

## Stop Conditions

Stop and re-plan if a change:

- contradicts ADR-006, non-superseded ADR-005, or ADR-004;
- lets a semantic operation bypass RouteDeck supervision;
- makes RouteDeck invoke product behavior directly;
- exposes a private identifier without current operation-specific permission;
- creates a second runtime, runner, navigation authority, conversation plane,
  or browser state authority;
- moves product prompt, graph, API, business logic, or UI into RouteDeck;
- turns diagnostics into product actions or chat context;
- introduces hidden fallback or substitute data;
- claims a test/release result without a current run;
- overwrites unrelated user work.

Implementation and verification run on the local Windows development machine.
Do not select or fall back to another host. Service commands and smoke URLs must
be reported whenever an application is started.
