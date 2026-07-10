# ADR-001: RouteDeck Is A LangGraph-Native Dynamic UI Application Framework

Status: Accepted
Date: 2026-07-06

2026-07-10 amendment: ADR-002 refines this direction into two adoption modes
over one interaction kernel. `compile()` returns a `RouteDeckCompiledApp`; its
`.runtime` is the shared `RouteDeckInteractionRuntime`, and Core Integration
constructs the same runtime with an existing-agent executor.

## Context

RouteDeck started as a product-neutral contract for graph-backed agentic UI:
manifests, projections, navigation state, action metadata, surfaces, review
staging, diagnostics, and frontend store/runtime contracts.

During the Corpus refactor, the boundary became confused in two directions:

- Corpus did too much RouteDeck work: projection assembly, surface assembly,
  action target duplication, context transport, and runtime wiring.
- A proposed correction pushed too much graph authority into RouteDeck, making
  it look like a new graph engine rather than a framework over an existing
  graph runtime.

The product vision is broader than a UI helper but narrower than a replacement
for LangGraph. RouteDeck should provide the backend and frontend application
framework required to deploy robust agentic applications with dynamic UI.
LangGraph should provide the graph execution foundation.

## Decision

RouteDeck will be a LangGraph-native application framework for dynamic agentic
UI.

RouteDeck depends on LangGraph for the Python backend execution foundation.
RouteDeck does not reinvent LangGraph's state machine, checkpointing,
branching, node execution, retries, tool execution, or streaming primitives.

RouteDeck provides the interaction governance layer above LangGraph:

- user-facing nodes and routes
- action metadata, params, forms, selectors, and hidden route actions
- dispatch validation before graph execution
- review and approval staging
- active surface and surface slot resolution
- projection/read-model generation
- browser location and frontend store sync
- streaming event protocol for dynamic UI
- reusable React/Vite frontend runtime
- deployment-oriented FastAPI runtime patterns

Custom LangGraph graphs are first-class. A developer may either:

1. Author a graph through RouteDeck's higher-level builder and let RouteDeck
   wire the standard LangGraph app shape.
2. Bring an existing custom LangGraph graph and attach RouteDeck interaction
   metadata, surface declarations, context providers, guard policy, and
   dispatch adapters.

The long-term direction may add Next.js/server-side runtimes and LangGraph
TypeScript support, but the first-class backend foundation is Python LangGraph.

## Authority Split

LangGraph owns execution truth:

- internal graph state mutation
- execution nodes
- branching and conditional edges
- checkpointing and recovery
- tool calls, LLM calls, database/API work
- private/internal nodes that do not need UI representation

RouteDeck owns interaction truth:

- user-facing node identity
- which operations may be requested from a user-facing node
- required parameters and form schema
- safety/review policy
- active/default surface rules
- URL/deeplink contract
- runtime projection shape
- frontend store protocol
- validation of user-facing dispatch requests

Product code owns domain truth:

- business handlers
- auth/workspace/account semantics
- product context facts
- product guard policy
- product surface components and product props
- durable persistence models

The key distinction is between execution nodes and interaction nodes. A
LangGraph graph may contain private execution nodes such as:

```text
validate_spec -> infer_auth -> generate_tools -> build_router_index -> persist_catalog
```

RouteDeck may expose that sequence as one user-facing interaction node or
operation:

```text
connection_configure + connection.activate
```

RouteDeck governs the interaction contract. LangGraph executes the internal
workflow.

## Architecture Pattern

The target application shape is:

```python
app = (
    RouteDeckApp("corpus")
    .state(AppGraphState)
    .nodes(APP_GRAPH_NODES)
    .flows(APP_GRAPH_FLOWS)
    .operations(APP_GRAPH_OPERATIONS)
    .surfaces(CORPUS_SURFACES)
    .context(CorpusContextProvider())
    .guards(CorpusGuardPolicy())
    .handlers(CORPUS_HANDLERS)
    .backend(RouteDeckSqliteBackend("corpus.db"))
)

compiled = app.compile()
runtime = compiled.runtime
```

At runtime:

```text
FastAPI request
  -> RouteDeck runtime
  -> validate interaction operation
  -> stage review if needed
  -> dispatch to compiled LangGraph executor
  -> receive state/events/effects
  -> validate returned user-facing state
  -> build RouteDeck projection
  -> stream/store response to frontend
```

The frontend consumes RouteDeck's projection/store protocol. Product React
components render product surfaces.

## Custom LangGraph Graphs

For custom graphs, RouteDeck must not require developers to rewrite their graph
inside RouteDeck. Instead, RouteDeck should support an adapter contract:

```python
class RouteDeckLangGraphAdapter:
    async def snapshot(self, context): ...
    async def dispatch(self, operation, state, payload, context): ...
    async def stream(self, operation, state, payload, context): ...
```

The adapter maps between:

- RouteDeck operation requests
- LangGraph input/state/config
- LangGraph streamed events
- RouteDeck action results and projections

This preserves custom graph structure while giving the app a standard
RouteDeck interaction runtime.

## Implications For Corpus

Corpus should migrate toward:

```text
Corpus LangGraph:
  execution flow, private nodes, business effects, persistence

Corpus RouteDeck app:
  interaction nodes, action metadata, surfaces, context lens, guards

RouteDeck runtime:
  validation, review, projection, surface assembly, store sync, streaming
```

The current Corpus runtime should be reduced over time. It should prepare
product facts, call LangGraph, and supply product policies/catalogs. It should
not manually own projection assembly, surface ordering, context transport, or
duplicated interaction graph metadata.

Known cleanup targets:

- make `ContextLens` first-class projection context instead of hiding it inside
  `projection.surfaces.side.props`
- move generic `SurfaceSpec` and surface slot assembly into RouteDeck
- separate product guard policy from runtime methods such as `_is_action_eligible`
- reconcile duplicated action target metadata with the RouteDeck interaction
  contract and LangGraph execution results
- keep product surface components and product props in Corpus

## Non-Goals

RouteDeck will not become a general graph engine independent of LangGraph.

RouteDeck will not own product business execution, database models, auth models,
LLM provider policy, or SaaS integration behavior.

RouteDeck will not force every LangGraph internal node to become a visible UI
node.

RouteDeck will not require a single generated graph shape for all products.
Custom LangGraph graphs remain first-class.

## Consequences

The older "optional LangGraph adapter" framing is superseded for the main
RouteDeck product direction. Small schema-only subpackages may remain
LangGraph-free if useful, but the backend framework runtime is LangGraph-native.

RouteDeck documentation and examples should move toward LangGraph-backed
application patterns. Existing FastAPI/React/Vite examples remain relevant as
transport and frontend shells, but the backend app model should assume
LangGraph.

Future Next.js/server-side and LangGraph TypeScript support should mirror this
architecture rather than invent a separate framework boundary.
