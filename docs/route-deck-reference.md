# RouteDeck Reference

Status: canonical framework reference
Date: 2026-06-03

Schema authority: `routedeck_core/models.py`

This file is the reference for RouteDeck framework language, ownership
boundaries, and common payload shapes. Product examples define their own domain
vocabulary, but RouteDeck framework terms follow this file and the schema names
in `routedeck_core/models.py`.

## Authority Order

1. `routedeck_core/models.py` defines enforceable schema names and fields.
2. This file defines the framework meaning, ownership, and usage of those
   schemas.
3. `docs/agentic-ui-state-runtime.md` defines the architecture direction.
4. Product specs, plans, and examples apply these terms inside product
   boundaries.

## Execution Owners

### Graph

The product-owned runtime that holds workflow truth, validates guards, enforces
permissions, and commits or rejects operations. The graph can be LangGraph,
another state machine, or product application code. RouteDeck does not replace
the graph.

### Product Runtime

The product-owned adapter that connects RouteDeck contracts to a product graph,
database, external API, auth policy, and side effects. A product runtime exposes
RouteDeck snapshots, projections, dispatch, streams, and introspection while
keeping business rules and private identifiers inside the product boundary.

Minimal runtime shape:

```python
class ProductRouteDeckRuntime:
    async def snapshot(self, context) -> RouteDeckRuntimeState: ...
    async def projection(self, context) -> RouteDeckProjection: ...
    async def dispatch(self, request, context) -> RouteDeckDispatchResult: ...
    async def inspect(self, query, context) -> RouteDeckIntrospection: ...
    def stream(self, context) -> AsyncIterator[RouteDeckEvent]: ...
```

### Product Agent

The product-owned LLM, planner, or assistant that consumes product planning
context derived from RouteDeck projection. A product agent chooses product
operations, binds visible entities, requests surface intents, or asks for
clarification. RouteDeck does not own product prompts, model calls, LLM
behavior, domain wording, or deterministic phrase routing.

### Planning Context

A product-owned view derived from RouteDeck projection and product state for a
product agent or product planner. Planning context includes only the context the
product is willing to expose to the agent: current node, current surface, legal
product operations, valid surface options, visible entities, and missing
arguments. RouteDeck defines projection terms; the product owns prompt-ready
summaries and entity-binding policy.

Example product-owned shape:

```json
{
  "current": {"node_id": "browse", "surface_id": "browse.product_list"},
  "legal_operations": [
    {"id": "catalog.open", "label": "View product", "required_args": ["product_ref"]}
  ],
  "surface_options": [
    {"surface_id": "browse.product_list", "label": "Product list"}
  ],
  "visible_entities": [
    {
      "kind": "product",
      "label": "Medusa T-Shirt",
      "operation_id": "catalog.open",
      "args": {"product_ref": "product_opaque_1"}
    }
  ]
}
```

Planning context is not a RouteDeck core schema. It is a product adapter layer
that protects the product agent from guessing hidden ids while keeping private
upstream identifiers out of ordinary chat text.

## Static Contract And Topology

### Manifest

The static RouteDeck contract for a product graph. `RouteDeckManifest` declares
possible nodes, edges, action specs, policies, and test paths. It is capability
shape, not live state.

Minimal manifest shape:

```json
{
  "version": "medusa-agent-slice3",
  "nodes": [{"id": "browse", "label": "Browse"}],
  "edges": [{"from_stage": "browse", "to_stage": "detail", "type": "action", "action_id": "catalog.open"}],
  "actions": [{"id": "catalog.open", "label": "View product", "category": "navigation"}]
}
```

### Navgraph

The RouteDeck-readable topology formed by manifest nodes and edges, plus the
current runtime location from projection navigation state. A navgraph answers:
where the product can be, how states connect, which transition is current, and
which transitions are reachable from the current graph state.

The navgraph is topology. It is not a command list, not a prompt, and not React
local state. Product UI renders it as a map or debugger surface only when that
surface is appropriate.

### Node

A graph location declared as `RouteDeckNodeSpec`. A node represents a workflow,
section, detail, or transient state that RouteDeck can project. Nodes declare
allowed actions and allowed/default surfaces.

Example:

```json
{
  "id": "detail",
  "label": "Product Detail",
  "allowed_actions": ["catalog.list", "variant.select", "cart.add_item"],
  "allowed_surfaces": {"active": ["product_detail"]},
  "default_surfaces": {"active": "product_detail"}
}
```

### Edge

A graph route declared as `RouteDeckEdgeSpec`. Edges describe navigation or
workflow transitions between nodes. Actions are not graph nodes. When a product
action triggers a graph transition, the edge records that action in `action_id`;
the action remains operation vocabulary and the edge remains graph topology.

Concrete rule: `catalog.open` is dispatched as an operation. The navgraph edge
`browse -> detail` records `action_id: "catalog.open"` so debuggers and tests can
explain why the transition exists. UI code must not render `catalog.open` as a
node in the navgraph.

Example:

```json
{"from_stage": "browse", "to_stage": "detail", "type": "action", "action_id": "catalog.open"}
```

### Action Spec

The static manifest declaration for an operation, represented by
`RouteDeckActionSpec`. An action spec says an action belongs to the product
contract. A runtime operation says the action is currently legal or available in
the current projection.

## Runtime State And Dispatch

### Runtime State

The current graph-backed RouteDeck state, represented by `RouteDeckRuntimeState`.
It includes the current `RouteDeckProjection`, runtime status, graph state, last
event, diagnostics, and metadata.

Example:

```json
{
  "projection": {"graph_node": "browse", "projection_version": 4},
  "status": "idle",
  "graph_state": {"node": "browse"}
}
```

### Projection

The client-facing view of runtime state, represented by `RouteDeckProjection`.
It includes current context, graph node, projection version, legal operations,
surfaces, presentation state, navigation state, and diagnostics. Projection is
output; it does not own graph behavior.

Example:

```json
{
  "current_context": "browse",
  "graph_node": "browse",
  "projection_version": 4,
  "legal_operations": [{"id": "catalog.open", "label": "View product"}],
  "surfaces": {"active": {"surface_id": "browse.product_list", "variant": "product_list"}},
  "navigation": {"current": {"node_id": "browse", "surface_id": "browse.product_list"}}
}
```

### Operation

A typed runtime action represented by `RouteDeckOperation`. Operations are the
things a product UI, product agent, or runtime client asks the graph/runtime to
dispatch. Operation metadata includes label, input schema, invocation kind,
dispatch readiness, required and missing args, safety class, execution mode,
guard text, target node, and surface id.

### Legal Operation

An operation the graph/runtime policy allows from the current state. A legal
operation is not automatically a button. Clients must still respect
`can_dispatch_now`, `invocation_kind`, `required_args`, `missing_args`,
`execution_mode`, and safety class.

### Product Operation

A product-facing operation such as `catalog.open` or `cart.add_item`. Product
operations describe user or business intent in product language. Product
operations have one of these concrete outcomes: they keep the current graph node,
transition to another graph node, update a projected surface, commit a side
effect, or return a guarded rejection.

### Dispatch

The generic operation submission path. Clients send a `RouteDeckDispatchInput`
and receive a `RouteDeckDispatchResult`. Dispatch validates setup, guards,
required args, safety policy, and graph state before accepting or rejecting the
operation.

Example request:

```json
{
  "operation_id": "cart.add_item",
  "args": {"variant_ref": "variant_opaque_1", "quantity": 1},
  "context": {"session_id": "demo-session"}
}
```

Example guarded result:

```json
{
  "operation_id": "cart.add_item",
  "accepted": false,
  "messages": [{"content": "Choose a variant and quantity before adding an item to cart."}],
  "events": [{"event_type": "guard_failure", "payload": {"message": "Choose a variant first."}}]
}
```

## Surfaces And Entity Binding

### Surface

A graph-projected UI region represented by `RouteDeckSurface`. Surfaces tell a
product shell what should be visible without making React local state the source
of workflow truth.

Common roles:

- `frame`: stable context around the main experience.
- `active`: current working surface.
- `diagnostic`: read-only inspection surface.

Common kinds:

- `peer`: alternate same-node view.
- `detail`: nested or review view.
- `embedded`: supporting inline view.

Example:

```json
{
  "name": "active",
  "surface_id": "detail.product_detail",
  "component": "MedusaProductDetail",
  "variant": "product_detail",
  "role": "active",
  "surface_kind": "peer",
  "props": {"product": {"title": "Medusa T-Shirt"}}
}
```

### Surface Intent

A product-agent or product-planner request to show one of the currently valid
product surfaces. Surface intent is product language over RouteDeck surface
options. Product agents choose a valid `surface_id` from planning context; they
do not expose or invoke `route.switch_surface` as ordinary shopper vocabulary.

Example:

```json
{"intent": "open_surface", "surface_intent": {"surface_id": "detail.product_detail"}}
```

### Visible Entity

A product-owned entity currently visible in projection or planning context, such
as a product, cart item, policy candidate, or execution trace. Visible entities
carry server-bindable operation arguments for the product runtime. They do not
expose private upstream identifiers, secrets, or raw framework diagnostics in
ordinary product UI or chat text.

### Selectable Entity

A visible entity that can be chosen for an operation requiring an entity
argument. Selectable entities bind user language to typed operation arguments
without inventing hidden ids or using a deterministic command router.

Example:

```json
{
  "kind": "variant",
  "label": "S / Black",
  "parent_label": "Medusa T-Shirt",
  "operations": [
    {"operation_id": "variant.select", "args": {"variant_ref": "variant_opaque_1"}},
    {"operation_id": "cart.add_item", "args": {"variant_ref": "variant_opaque_1", "quantity": 1}}
  ]
}
```

## Navigation And Client State

### Navigation State

The projected browser/runtime location represented by `RouteDeckNavigationState`
and `RouteDeckLocation`. It tracks current node/surface params, back stack,
forward stack, and whether back/forward/cancel are legal.

Example:

```json
{
  "current": {"node_id": "detail", "surface_id": "detail.product_detail"},
  "back_stack": [{"node_id": "browse", "surface_id": "browse.product_list"}],
  "forward_stack": [],
  "can_go_back": true,
  "can_go_forward": false,
  "can_cancel": true
}
```

### Internal Route Operation

A framework/runtime navigation operation such as `route.open_node`,
`route.switch_surface`, `route.back`, `route.forward`, or `route.cancel`.
Internal route operations are for browser replay, history, recovery, diagnostics,
or runtime plumbing. Product integrations keep them hidden from ordinary product
UI and product-agent planning context unless the current surface is explicitly a
developer or diagnostic surface.

### RouteDeckStore

The framework client-side state store, exposed by `@routedeck/react`, that holds
the current projection, runtime status, pending operation, navigation state, and
last event for React clients. RouteDeckStore mirrors RouteDeck runtime state for
rendering and dispatch. It is not the graph source of truth and does not replace
product runtime validation.

## Diagnostics, Streams, And Boundaries

### Diagnostics And Introspection

Read-only explanation surfaces and APIs. `RouteDeckIntrospection` reports current
node, reachable nodes, legal operations, blocked operations, guard explanations,
surfaces, route traces, and diagnostics. Diagnostics expose framework details;
ordinary product UI uses product language.

### Events And Streams

Runtime events are represented by `RouteDeckEvent`. RouteDeck streams emit state
events such as `projection_update`, `operation_started`, `operation_completed`,
`graph_transition`, `guard_failure`, `surface_update`, and `runtime_status`.
Product-agent text streams are separate product-owned streams.

### Product Boundary

RouteDeck owns the reusable state, projection, navigation, navgraph, dispatch,
surface, diagnostics, introspection, and client-store contracts. Products own
domain vocabulary, prompts, planning-context construction, product agents,
product runtimes, domain data, auth, persistence, business policy, product
routes, product UI copy, LLM calls, and domain side effects.
