# RouteDeck Agentic UI State Runtime

Status: Canonical framework direction
Date: 2026-05-19

RouteDeck is graph-backed state management for agentic UI.

For the canonical framework reference, read `docs/route-deck-reference.md`.
For a practical operator, agent, and developer guide, read `docs/using-routedeck.md`.

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

Surfaces and chat share the same semantic capability layer. A surface button,
form, or selector and a chat request must resolve to the same product operation,
entity key, and runtime dispatch path. Component-local behavior such as hover,
scroll, focus, and visual expansion stays local to the component; semantic
actions such as selecting a variant, opening a product, approving a proposal, or
adding an item to cart go through RouteDeck dispatch.

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

## Internal Navigation Operations

RouteDeck may define generic route operations such as:

- `route.open_node`
- `route.switch_surface`
- `route.back`
- `route.forward`
- `route.cancel`

These are framework/runtime primitives for browser replay, history, diagnostics,
and validated internal navigation. Product integrations should normally mark
them as `invocation_kind=hidden` and keep them out of ordinary product quick
actions and normal product-agent planning context.

A product agent should choose product operations or product surface intents. The
product runtime can map a validated surface intent to an internal route
operation. This keeps product chat natural while preserving graph-owned
navigation validation.

## Surfaces

Surfaces are graph-declared and RouteDeck-projected. They are not arbitrary React children invented by product code after the fact.
Surfaces present runtime capabilities; they do not own the capabilities.

Surface roles:

- `frame`: contextual UI around the central product experience
- `active`: opened after user initiation, accepted proposal, or graph-required recovery
- `diagnostic`: developer/read-only inspection UI

Corpus or another product agent may choose an allowed surface variant, but RouteDeck validates that choice against the current graph node. Surface choices are sticky presentation state until a graph transition, user request, or component event changes them.

Presentation state is ephemeral and browser/session scoped. It is not product graph truth.

Surface affordances declare semantic interactions emitted by a surface. An
affordance carries an `affordance_id`, optional `entity_key`, event payload, and
target product operation or surface intent. The product runtime resolves the
binding from current planning context, dispatches through RouteDeck, and then
publishes a new projection.

Entity binding is product-owned and shared by surfaces and chat:

```text
label: user/agent text, for example "Medusa T-Shirt"
entity_key: context-local binding key, for example "product:medusa-shirt"
opaque ref: runtime dispatch arg, for example "product_opaque_1"
```

The agent should select from available entities in planning context. A rendered
surface should emit the same entity key when the user clicks the corresponding
UI. The runtime remains the authority and revalidates operation legality,
permissions, setup, and arguments before committing.

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
- graph-node selection is read-only inspection; it does not dispatch, navigate,
  mutate graph state, or update the browser URL
- operation labels, entity labels, affordances, deeplinks, and edge metadata
  belong in a read-only inspector or diagnostics surface next to the graph

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
Corpus also demonstrates the preferred browser deeplink split: graph location is
encoded in product-owned path segments such as `/app/home` or
`/app/agents/:agent_id/:node_id`, while query params are reserved for optional
surface state such as `surface_id`.

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
When a product renders action chips, those chips are a product-curated
chat/assistant control surface outside the navgraph. In the Corpus pattern,
chips attach to the latest assistant turn or active composer context. They
filter hidden/internal `route.*` operations, respect dispatch readiness, and
share the same operation/entity paths available to chat planning context.
They also filter normal current-node no-op operations unless the product
explicitly presents them as refresh/reload controls. Product surfaces are
separate from the navgraph and inspector: product UI emits declared surface
affordance events, and the navgraph updates only after dispatch/projection
state changes.

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
