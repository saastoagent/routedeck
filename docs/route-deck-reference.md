# RouteDeck Reference

Status: canonical framework reference

Implementation authority: `routedeck_core/app`, `routedeck_core/contracts`,
`routedeck_core/state`, `routedeck_core/supervision`, and
`routedeck_core/navigation`.

This document describes the one standalone compiled RouteDeck runtime and its
canonical contracts.

## Core Vision

RouteDeck is the state and interaction authority for an agentic application.
It lets a product expose dynamic UI and agent tools without letting either the
UI or the model own application truth.

The framework owns:

- immutable application and frontend contracts;
- canonical session, conversation, operation, review, navigation, and public
  surface state;
- provider and guard execution around one supervised operation runner;
- durable state, attempts, results, events, replay, leases, and private blobs;
- default-deny public projection and model context;
- shareable/session-bound deep links and exact history;
- generic HTTP/SSE, headless TypeScript, and React primitives.

The consuming application owns:

- domain APIs, typed adapters, wire models, business validation, and side
  effects;
- prompts, model selection, LangGraph topology, and public chat behavior;
- product copy, recovery wording, route-entry resolution, and visual
  components;
- authentication and deployment policy around the generic RouteDeck ports.

RouteDeck contains no Medusa, commerce, or other product-specific branches.

## Application Contract

### `ApplicationSpec` and `FeatureSpec`

An application is a name, an entry node, feature modules, and optional
cross-feature transitions. Each `FeatureSpec` owns a unique namespace, its
nodes, and only transitions whose source and target both belong to that
feature. The application composition root declares cross-feature transitions.

`compile_app(...)` produces one `CompiledRouteDeckApp` containing:

- flattened, validated nodes and transitions;
- canonical operation, provider, guard, capability, and surface catalogs;
- compiled route codec;
- versionable frontend contract;
- derived executable paths for transitions, deep-link policy, safety, review,
  and recovery branches.

Compilation fails on duplicate or conflicting identifiers, overlapping routes,
unknown references, out-of-scope providers/guards, undeclared outcomes,
ambiguous branches, unreachable nodes, invalid route entries, invalid public
schemas, or incomplete write-recovery declarations.

### `NodeSpec`

A node is a product-facing location, not a LangGraph node. It declares:

- stable ID, title, kind, optional parent, and `RouteSpec`;
- optional `RouteEntrySpec`;
- context and entity providers;
- guards and operations executable at that location;
- capabilities and `SurfaceSlotsSpec`;
- navigation and recovery policies;
- explicitly public metadata.

The navgraph is the compiled set of nodes plus exact operation/outcome
transitions. An operation outcome has exactly one target. A node can map to a
workflow step, section, detail page, or transient result without mirroring any
model-orchestration graph.

### `RouteEntrySpec`

A route entry declares how an incoming path becomes an authoritative product
operation:

```python
entry=RouteEntrySpec(
    operation=OPEN_PRODUCT_BY_ROUTE.ref,
    outcome="opened",
    bindings=(
        RouteParameterBinding(
            parameter="product_handle",
            argument="product_handle",
        ),
    ),
)
```

Every path parameter must be bound exactly once to a declared operation input.
The compiler materializes the exact self-transition for the entry outcome.
RouteDeck owns structural route parsing and the supervised operation call; the
product handler owns domain resolution. There is no regex, text heuristic, or
entity scan that substitutes for a declared binding.

### Operations, providers, guards, and capabilities

`OperationSpec` declares an ID, title, description, default-deny input schema,
safety class, outcomes, output schemas, provider and guard references, entity
inputs, review policy, recovery metadata, and public metadata.

Providers load operation-scoped facts or entity allowlists. Guards decide from
those typed facts whether an operation can execute. Capabilities group
operations and surfaces for inspection/model context; they do not create a
second execution path.

`bind_app(...)` requires exactly one typed async handler for every operation,
provider implementation for every provider, and guard implementation for every
guard. Missing, extra, synchronous, or incorrectly shaped bindings are startup
errors.

## Surface Contract

### `SurfaceSpec`

A surface declares:

- a stable framework ID;
- a product-owned component name;
- `stable` or `ephemeral` lifecycle;
- operation-backed affordances;
- a strict public props JSON schema;
- optional server-only private-form authorization.

Public object schemas require explicit types, explicit properties, and
`additionalProperties: false`. Unsupported schema keywords and undeclared
shape are rejected during construction.

`SurfaceSlotsSpec` places surfaces into `active`, `frame`, `peer`, `detail`,
`form`, `review`, `status`, `error`, or `diagnostic`. The frontend contract
exports IDs, components, lifecycles, public schemas, affordances, routes, and
operations. Product React components are registered separately by component
name.

A surface affordance names a semantic UI event and, when state-changing, an
exact operation. `RouteDeckSurfaceHost` resolves the affordance from the
compiled contract and sends it through the same dispatch path as an agent tool.
Raw UI events do not become application truth or model instructions.

### Stable and ephemeral state

Canonical public surface state is stored in the RouteDeck session.

- Stable surface state survives navigation even when the target node does not
  render that surface. This lets exact history restore the prior product view.
- Ephemeral surface state survives only while the current node declares that
  surface. The React host also keys ephemeral rendering by projection version,
  so local component state resets when the projection changes.

Every stored surface ID must exist in the compiled global catalog. Duplicate or
unknown surface state fails validation.

### Private forms

Private fields are not public surface props. A private-form surface declares a
`PrivateFormBindingSpec` containing:

- the exact public prop that carries its opaque form handle;
- the exact allowed top-level private field names.

That binding is server-only and is excluded from the exported frontend
contract. The generic FastAPI transport authorizes a requested handle against
the current declared/projected surface before any read or write.

An authorized untouched form returns a no-store snapshot with revision `0`,
`complete: false`, and `{}`. The first real save atomically records revision
`1`, field names, completeness, the new session state, and an encrypted private
blob. Later saves increment the revision. Unexpected fields, forged handles,
version conflicts, or a draft/blob mismatch fail loudly.

Private values never enter public projection, contract export, public events,
inspection, or model context. Every private-form response requires
`Cache-Control: no-store`.

## State And Supervision

### Canonical session

`RouteDeckSession` is immutable and versioned. It contains:

- schema and navgraph versions;
- session, projection, and event versions;
- current location plus exact back/forward stacks;
- durable finalized/interrupted conversation turns;
- private state: drafts, entity bindings, resume capabilities, configuration;
- public state: opaque entities, surfaces, status, failure, disabled operations;
- active operation, pending review, and journaled result state.

`RouteDeckSessionAggregate` exposes named domain actions that apply explicit
events and enforce invariants over the immutable session. UI state, a LangGraph
checkpoint, or an external API response is not an alternate session authority.

### One operation path

`RouteDeckOperationRunner` is the only execution path for surface, agent,
route-entry, system, and recovery operations. It:

1. loads and validates the current session contract;
2. claims the parent turn/request with a fingerprint and expected version;
3. loads declared providers and evaluates declared guards;
4. stages required review or claims external execution;
5. journals delivery evidence and typed result before applying effects;
6. atomically commits session, attempt/result, and public events;
7. notifies live subscribers after persistence.

Repeated request IDs with the same fingerprint are idempotent. Reuse with a
different fingerprint, concurrent ownership, stale versions, stale/expired
review, or an invalid effect is a typed conflict.

Session creation, navigation, private-form saves, and chat turns use the same
request-identity rule through a durable mutation journal. Their public-safe
terminal result, committed session/projection versions, and event cursor are
stored atomically with canonical state. Exact replay returns the recorded
result without repeating navigation, model, or product work; conflicting reuse
fails with `request_id_reused`.

### External writes and review

External writes declare recovery metadata. RouteDeck distinguishes:
`not_sent`, `possibly_sent`, and `response_received`. If a process cannot prove
whether an external write happened, it records `external_outcome_unknown` and
exposes the declared product recovery operation. It does not retry the affected
write, invent success, or switch providers.

An operation with `ReviewPolicy.REQUIRED` produces a durable proposal tied to
the operation spec version, authoritative context fingerprint, projection
version, and expiry. Accept/reject uses separate versioned requests. Acceptance
rechecks the current context before executing the original write.

## Projection And Events

`ProjectionProjector` emits only declared public data:

- current location and route parameters;
- exact navigation identity and availability;
- currently legal operations;
- opaque public entity handles and allowed values;
- projected surfaces and public props;
- status, safe failure, and limited diagnostics.

Private IDs remain in server-side bindings. Product handlers receive the
private identifier only after the requested opaque handle, entity kind, current
operation, and allowlist all match.

Canonical events carry monotonically increasing cursors and are persisted with
the state transition before live fanout. SSE reconnect replays after the last
cursor. A cursor outside retention produces an explicit reset so the client
resynchronizes from the session endpoint.

A private-form save emits `private_form_changed` with public revision metadata
only. The form identifier and encrypted values are never written to the public
event log.

The headless TypeScript store rejects regressing or gapped versions, schedules
an authoritative resync, and never treats an optimistic browser mutation as a
confirmed projection. When delivery becomes outcome-unknown, the client
retains the immutable request ID and payload and blocks a conflicting payload
until the application explicitly retries that exact request or abandons it and
resynchronizes.

For mutations, a received `4xx` contract/conflict response is a confirmed
rejection. A `5xx`, lost response body, malformed response contract, or invalid
success envelope is outcome-unknown because the server may already have
committed; the client retains the original request identity for replay.

SSE transport failures may reconnect, but `404 session_not_found` and
`410 session_expired` are terminal. The stream stops and exposes an error
instead of polling a permanently unavailable session.

## Deep Links And Exact History

### Route policies

Routes are compiled from normalized segment templates. Route parameter values
are decoded as UTF-8, cannot contain path separators, and must match the exact
declared parameter set.

- `shareable` routes can open without an existing guest session. Dynamic keys
  are validated by the product or resolved through a declared route-entry
  operation.
- `session_bound` routes require an authenticated guest session and an
  unexpired opaque `resume_handle` whose session, node, and exact route
  parameters match.

Resume capability values are secret-bearing navigation credentials. They are
projected only as the current link handle and never inferred from a route name.

### Navigation transaction

The generic navigation endpoint accepts one declared intent:

- `open_path`
- `back`
- `forward`
- `cancel`
- `restore_history_entry`

The server validates the expected session version, canonical path, deep-link
authorization, node policy, public key, and history identity before committing
the location, retained surface state, and event.

Each canonical location has a positive unique `entry_id`. Browser history
stores only that RouteDeck identity plus the canonical URL. A `popstate`
restores the exact matching server entry and verifies that its path matches;
RouteDeck does not guess direction or replay commerce commands. Missing,
duplicate, unknown, or path-mismatched identities fail.

On bootstrap, the headless store captures the incoming URL before loading or
creating the guest session, reconciles that URL through the navigation API, and
only then writes the confirmed canonical projection to browser history. Normal
confirmed transitions push; bootstrap/reconnect and explicit replacement use
replace. Back/forward operate through browser history and return through exact
server restoration.

## LangGraph Adapter

RouteDeck's navgraph and a LangGraph model graph have different jobs.

- RouteDeck navgraph: durable product location, legal operations, review,
  history, and UI projection.
- Product LangGraph: model/tool orchestration chosen by the application.

`RouteDeckMiddleware` loads the current session before a model call, rebuilds
durable finalized messages, injects a default-deny JSON context, and filters
the model's tools to currently legal RouteDeck operations.
`RouteDeckToolWrapper` validates the invocation context and sends tool calls
through `RouteDeckOperationRunner`. Tool observations become durable turns only
through the supervised parent-turn lifecycle.

The application retains its existing `create_agent(...)` or raw `StateGraph`.
For raw graphs, use the wrapper around `ToolNode` tool calls. RouteDeck does not
accept a `StateGraph` and does not synthesize or mutate topology. No topology
builder is exported: the RouteDeck navgraph and the product orchestration graph
remain separate authorities for separate concerns.

## Generic HTTP Plane

`routedeck_fastapi` mounts product-neutral endpoints under `/api/routedeck`:

| Endpoint | Purpose |
| --- | --- |
| `GET /contract` | Compiled frontend contract. |
| `POST /sessions` | Create a guest session and run the injected initializer. |
| `GET /session` | Current public projection. |
| `POST /navigation` | Versioned exact navigation transaction. |
| `POST /dispatch` | Versioned surface operation. |
| `POST /reviews/{id}/accept` | Accept a current proposal. |
| `POST /reviews/{id}/reject` | Reject a current proposal. |
| `GET /events` | Replayable typed public SSE. |
| `GET|PUT /private-forms/{id}` | No-store encrypted private-form channel. |
| `GET /inspect` | Public runtime topology and diagnostics. |

The product injects the compiled app, runner, store, notifier, projector,
private-form codec, session factory, initializer, and navigation runner through
`RouteDeckDependencies`. A missing dependency returns a visible unavailable
failure; the transport never constructs a hidden store, model, or product
adapter.

Product chat is a separate API plane because the prompt, model, streaming
events, and assistant behavior are product-owned. The Medusa reference mounts
`POST /api/medusa-agent/chat` alongside the generic RouteDeck plane.

## Headless And React Packages

`@routedeck/core` provides:

- strict decoders generated from Python contracts;
- credential-aware HTTP and SSE clients;
- authoritative event/session store with replay and resync;
- route codec, browser-history adapter, and navigation reconciliation;
- isolated private-form client state.

`@routedeck/react` provides:

- `RouteDeckProvider` and selectors/hooks;
- `RouteDeckSurfaceHost` plus a product component registry;
- private-form, review, navigation, status, and error primitives;
- a lazy React Flow navgraph primitive that renders the complete compiled
  transition sitemap, highlights the current and currently reachable nodes,
  and inspects each node's route, deep-link policy, surfaces, operations, and
  outgoing transitions.

The generated frontend contract contains the complete product-neutral
transition set. Consumers never hardcode inspector edges or reconstruct the
navgraph from URLs. `RouteDeckNavGraph` reads that contract plus the canonical
projection and always renders the full Navgraph, with current and reachable
nodes highlighted in place. The same complete graph can be expanded for closer
inspection.

React owns rendering and component-local interaction state. It does not own
canonical operation state, infer legal actions, or call product domain APIs.

## Failure Semantics

Required configuration, schemas, adapters, routes, bindings, versions, and
invariants fail loudly. RouteDeck does not silently switch to an in-memory
store, alternate model/provider, cached response, fixture, empty result,
heuristic router, or generic success. Optional behavior must be explicit in a
contract or caller choice.

Failures exposed publicly contain a stable kind/code/phase, correlation ID, and
safe message. Raw exceptions, HTTP response bodies, private IDs, credentials,
and private-form values stay server-side.

## Medusa Reference Proof

The reference app composes catalog, cart, checkout, and order `FeatureSpec`s
over this kernel. Its real local flow covers product browse/detail, exact
variant selection, cart mutation, private contact, shipping, system/manual demo
payment, reviewed order placement, uncertain-write reconciliation,
confirmation, reload, shareable/session-bound links, and exact history.

The typed Store client and all commerce handlers remain in the Medusa package;
the browser has no Store API path. See
[`medusa-agent-reference-app.md`](medusa-agent-reference-app.md) and
[`../examples/medusa-agent/README.md`](../examples/medusa-agent/README.md).

This reference describes implemented contracts, not a release-pass claim. A
live-model release smoke requires an explicit `OPENAI_API_KEY` and must be
reported from a current release run.
