# RouteDeck Agentic UI State Runtime

Status: Canonical framework direction
Date: 2026-05-19

RouteDeck is graph-backed state management for agentic UI.

It sits in the same broad mental category as Redux, MobX, Zustand, or other React state-management systems, but it is not a direct clone of any of them. Those tools manage UI/application state through stores, reducers, observables, or selectors. RouteDeck manages application state where the source of truth is a graph runtime, commonly LangGraph, and where an agent or UI component dispatches typed operations that the graph validates before committing.

The core idea:

```text
Graph owns truth.
RouteDeck owns the generic agentic UI state runtime over that graph.
RouteDeckStore exposes that runtime to React.
Product agents and product UI consume the store.
```

RouteDeck is not a product shell, a projection DTO, a debugger-only package, or a workflow-builder metaphor. Projection and diagnostics are outputs of the runtime-store model.

## State-Management Analogy

```text
Redux state      -> RouteDeckRuntimeState
Redux action     -> RouteDeckDispatchInput / RouteDeckOperation
Redux reducer    -> graph kernel or LangGraph adapter
Redux selector   -> RouteDeck hooks/selectors
Redux middleware -> guards, autonomy policy, stream adapters, persistence adapters
Redux DevTools   -> RouteDeck diagnostics and introspection
```

The runtime stack:

```text
Graph runtime
  -> RouteDeckRuntime adapter
    -> RouteDeckRuntimeState
      -> RouteDeckStore
        -> React hooks
          -> product UI, product agents, diagnostics
```

## Framework Boundaries

RouteDeck framework code owns product-neutral contracts and utilities:

- `RouteDeckProjection`
- `RouteDeckSurface`
- `RouteDeckOperation`
- `RouteDeckEvent`
- `RouteDeckRuntimeState`
- `RouteDeckDispatchInput`
- `RouteDeckDispatchResult`
- `RouteDeckRuntimeStatus`
- `RouteDeckIntrospection`
- `RouteDeckRuntime`
- `RouteDeckStore`

RouteDeck framework code must not own:

- product prompts
- product copy
- product auth semantics
- product database models
- product-specific route literals
- product-specific node ids
- raw LLM provider calls
- created SaaS Agent runtime behavior

Product literals such as SaaStoAgent, Corpus, SaaSAgent, auth route names, or specific workflow ids belong in product adapters, product tests, product examples, or product docs. They do not belong in reusable RouteDeck runtime source.

## Backend Runtime Contract

The backend split should stay explicit:

```text
routedeck_core
  product-neutral models, protocols, projection/runtime contracts

routedeck_langgraph
  optional LangGraph adapter implementing RouteDeckRuntime

product backend
  product graph, domain handlers, auth, persistence, prompts, LLM calls

product RouteDeck adapter
  translates product graph state into generic RouteDeck runtime state
```

Target protocol shape:

```python
class RouteDeckRuntime:
    async def snapshot(context) -> RouteDeckRuntimeState: ...
    async def projection(context) -> RouteDeckProjection: ...
    async def dispatch(input, context) -> RouteDeckDispatchResult: ...
    async def inspect(input, context) -> RouteDeckIntrospection: ...
    async def stream(context) -> AsyncIterator[RouteDeckEvent]: ...
```

The graph kernel validates operations, enforces guards, commits transitions, and returns recovery context. RouteDeck wraps that behavior in a reusable state-management contract. It does not bypass the graph.

## React Store Contract

`@routedeck/react` exposes a real store, not only a passive provider:

```ts
type RouteDeckStore = {
  getState(): RouteDeckClientState
  subscribe(listener: () => void): () => void
  refresh(): Promise<void>
  dispatch(input: RouteDeckDispatchInput): Promise<RouteDeckDispatchResult>
  connectStream(): () => void
  inspect(input: RouteDeckInspectInput): Promise<RouteDeckIntrospection>
}
```

The provider mounts a configured store:

```tsx
<RouteDeckProvider store={routeDeckStore}>
  <App />
</RouteDeckProvider>
```

Core hooks:

- `useRouteDeckStore()`
- `useRouteDeckProjection()`
- `useRouteDeckSurface(name)`
- `useRouteDeckOperations()`
- `useRouteDeckOperation(id)`
- `useRouteDeckDispatch()`
- `useRouteDeckStatus()`
- `useRouteDeckDiagnostics()`
- `useRouteDeckInspect()`

The default HTTP/SSE implementation is a transport adapter:

```ts
createRouteDeckStore({
  snapshotUrl,
  dispatchUrl,
  streamUrl,
  inspectUrl,
})
```

It knows how to fetch, dispatch, subscribe, and inspect. It does not know product behavior.

## Runtime State

`RouteDeckRuntimeState` is the state-management object. A projection is only one part of it.

It should include:

- current projection
- runtime status
- current graph snapshot reference
- projection version
- active turn or operation id
- legal operations
- surface state
- ephemeral presentation state
- diagnostics summary
- recent events or stream status
- latest dispatch result or error

Runtime status should distinguish states such as:

- `idle`
- `refreshing`
- `streaming`
- `dispatching`
- `committing`
- `recovering`
- `failed`

## Operation Flow

RouteDeck dispatch is the generic action path:

```text
UI or product agent chooses a typed operation
  -> RouteDeckStore.dispatch(input)
    -> backend RouteDeckRuntime.dispatch(input)
      -> product graph validates guards
        -> graph commits, rejects, or asks for review
          -> RouteDeckRuntimeState is rebuilt
            -> RouteDeckStore publishes state
              -> React subscribers update
```

LLMs do not patch graph state. They choose typed legal operations. Hard graph guards always win.

Operation metadata should include:

- operation id
- label and description
- input schema
- invocation kind: `direct`, `form`, `entity_selector`, `surface`, or `hidden`
- dispatch readiness: `can_dispatch_now`, `required_args`, and `missing_args`
- safety class
- execution mode: `auto`, `review`, or `blocked`
- guard explanation
- required context

`legal_operations` means the graph policy allows the operation from the current state. It does not mean a generic UI chip may dispatch the operation immediately. Shells must check `can_dispatch_now` before one-click dispatch and use `invocation_kind` to choose the interaction: direct execution, form/proposal, entity selection, surface opening, or hidden runtime-only handling.

Safe navigation and state-selection operations may be committed during an agent turn when `can_dispatch_now=true`. Side-effectful operations produce proposals or review surfaces and require an acceptance/action path.

## Surfaces

Surfaces are graph-declared and RouteDeck-projected. They are not arbitrary React children invented by product code after the fact.

Surface roles:

- `frame`: contextual UI around the central product experience
- `active`: opened after user initiation, accepted proposal, or graph-required recovery
- `diagnostic`: developer/read-only inspection UI

Corpus or another product agent may choose an allowed surface variant, but RouteDeck validates that choice against the current graph node. Surface choices are sticky presentation state until a graph transition, user request, or component event changes them.

Presentation state is ephemeral and browser/session scoped. It is not product graph truth.

## Streams

RouteDeck streams are state streams:

```text
projection_update
operation_started
operation_completed
graph_transition
guard_failure
surface_update
runtime_status
diagnostic_update
```

Product-agent streams are separate. In SaaStoAgent, Corpus text/proposal streaming is not the RouteDeck stream. Both streams can share `turn_id` and `projection_version`.

## Diagnostics and Introspection

Diagnostics is the RouteDeck DevTools layer. It is read-only.

The same introspection source should power both developer diagnostics and LLM meta tools.

Minimum introspection output:

- current node
- reachable nodes
- legal operations
- blocked operations with reasons
- guard explanations
- surface projection state
- route trace
- why-not-reachable explanation
- recent runtime events

Navigation graph diagnostics should show navigation nodes and navigation edges only. Do not draw actions as graph edges. Actions belong in selected-node inspection details or operation diagnostics.

Focused current-node diagnostics should use compact lane-separated routing:

- incoming edges terminate on distinct target lanes
- outgoing edges start from distinct source lanes
- opposite-direction node pairs do not reuse the same path geometry
- routing stays compact and curved rather than switching to large orthogonal
  elbows

The full graph view should be the navgraph: a root-centered map of graph state
and semantic route edges.

- the root or home-equivalent node is visually central when present
- first-hop hubs are emphasized on the primary ring
- deeper supporting nodes expand outward within their branch sector
- detached components can sit on outer spokes instead of pretending to fit a
  false hierarchy
- all nodes and semantic route edges remain visible
- labels and action details stay out of the canvas when they create clutter

## SaaStoAgent Consumption Pattern

SaaStoAgent consumes RouteDeck like an application consumes a state manager:

```text
CorpusGraphRuntime
  -> SaaStoAgent RouteDeck adapter
    -> generic RouteDeckRuntime
      -> RouteDeckStore
        -> Corpus shell, contextual surfaces, diagnostics
```

Corpus is the SaaStoAgent product agent. Corpus reads RouteDeck state and dispatches RouteDeck operations. It does not own RouteDeck state management.

Corpus owns:

- user intent interpretation
- assistant text streaming
- platform-agent prompts and policies
- legal operation selection
- visible proposals
- allowed surface variant choice

RouteDeck owns:

- state store
- projection
- legal operation exposure
- dispatch
- surface projection
- diagnostics
- introspection

The product UI must not render `legal_operations` directly as default action chips. Visible choices should be Corpus-authored proposals, initiated surfaces, or diagnostics.

## Implementation Plan Incorporated

The current reset combines two accepted plans:

1. RouteDeck + SaaStoAgent reset:
   - remove product-runtime leakage from RouteDeck
   - keep legal operations internal/runtime-facing
   - split Corpus, RouteDeck, and diagnostics streams
   - make diagnostics richer than raw JSON
   - remove `/api/app/graph/*` from the product path
   - keep Corpus central

2. RouteDeck runtime-store implementation:
   - add backend runtime state and dispatch contracts
   - add `RouteDeckStore` and generic HTTP/SSE store factory
   - mount SaaStoAgent on a configured store
   - move dispatch/state/introspection behavior into a product adapter
   - keep Corpus chat streaming separate from RouteDeck state streaming
   - remove duplicated frontend projection/state juggling

This is the anti-drift target. Future patches should extend this shape instead of reintroducing passive projection plumbing or product-specific RouteDeck code.

## Anti-Drift Rules

Do:

- treat RouteDeck as graph-backed state management
- keep RouteDeck framework code product-neutral
- let graph adapters implement product-specific runtime behavior
- expose operations to agents and diagnostics
- render product choices as proposals or initiated surfaces
- keep diagnostics read-only
- keep presentation state ephemeral
- verify the app through store state, dispatch, streams, and introspection

Do not:

- treat RouteDeck as only a projection response
- hide RouteDeck inside Corpus
- put SaaStoAgent literals in RouteDeck framework source
- render legal operations as product UI by default
- draw actions as nav-graph edges
- let diagnostics execute operations
- let LLMs patch graph state directly
- let React components invent graph truth outside RouteDeck
