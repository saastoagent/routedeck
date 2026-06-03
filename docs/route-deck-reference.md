# RouteDeck Reference

Status: canonical framework reference
Date: 2026-06-03

Schema authority: `routedeck_core/models.py`

This file is the north-star reference for RouteDeck framework language,
ownership boundaries, capability semantics, and payload shapes. Product examples
define their own domain vocabulary. RouteDeck framework terms follow this file
and the schema names in `routedeck_core/models.py`.

## Authority Order

1. `routedeck_core/models.py` defines enforceable schema names and fields.
2. This file defines framework meaning, ownership, and usage.
3. `docs/agentic-ui-state-runtime.md` explains the architecture direction.
4. Product specs, plans, and examples apply these terms inside product
   boundaries.

## Core Vision

RouteDeck lets products and agents present dynamic UI without letting UI own
application truth. A surface can wrap a developer-authored component or an
agent-generated component, but every semantic interaction from that surface goes
through declared capabilities and runtime validation.

RouteDeck's spine:

```text
Product graph truth
  -> RouteDeck navgraph
  -> capability contract
  -> RouteDeck projection
  -> surfaces, chat, automation, diagnostics
  -> affordance event or agent-selected capability request
  -> RouteDeck dispatch
  -> graph commit, rejection, review, or recovery
  -> semantic observation and next projection
```

Core rules:

- The product graph owns truth.
- RouteDeck exposes a navgraph that orients agents and users inside the product.
- RouteDeck projects graph-backed state, navgraph location, and valid capabilities.
- Surfaces present capabilities; they do not own capabilities.
- Chat invokes the same capabilities that surfaces present.
- Every semantic interaction that changes app state, agent state, or workflow
  position from a surface must also be available through product-agent planning
  context.
- Component-local behavior such as hover, scroll, focus, visual expansion, and
  in-progress typing is not a RouteDeck capability until the product promotes it
  into surface/session state or graph state.

## Truth And State Layers

### Graph State

Authoritative product state held by the product graph or product runtime. Graph
state includes workflow position, committed business state, permissions, guard
state, and side-effect status. RouteDeck does not mutate graph state directly;
RouteDeck dispatch asks the product runtime to validate and commit.

Example:

```json
{"node": "cart", "cart_ref": "cart_opaque_1", "selected_variant_ref": "variant_opaque_1"}
```

### Projection

The client-facing view of runtime state, represented by `RouteDeckProjection`.
Projection includes current context, RouteDeck/navgraph node, projection version,
legal operations, surfaces, presentation state, navigation state, and diagnostics.
Projection is output. It does not own graph behavior.

Schema note: `graph_node` names the current RouteDeck/navgraph node in the
projection. It is not required to be the product graph's internal execution
state.

Example:

```json
{
  "current_context": "detail",
  "graph_node": "detail",
  "projection_version": 8,
  "legal_operations": [{"id": "cart.add_item", "label": "Add to cart"}],
  "surfaces": {"active": {"surface_id": "detail.product_detail", "variant": "product_detail"}},
  "navigation": {"current": {"node_id": "detail", "surface_id": "detail.product_detail"}}
}
```

### Component Local State

Ephemeral state owned by a rendered component. Examples: hover, focus, scroll,
accordion expansion, unsent keystrokes, pointer location, and local animation
state. Component local state does not enter planning context and does not update
agent context.

### Surface Session State

Resumable state for a surface or session that is not yet committed graph truth.
Examples: selected variant before add-to-cart, a draft form, a review proposal,
or a chosen peer-surface variant. Surface session state is represented through
projection props, `presentation_state`, or product runtime session state. The
product runtime decides when a surface/session value graduates into graph state.

### Agent Context

Product-owned turn context and memory used by the product agent. Agent context
updates from planning context, user messages, runtime results, and semantic
observations. Raw UI events do not enter agent context.

## Navgraph And Capability Contract

### Navgraph

The RouteDeck navigation topology exposed to agents, users, and diagnostics. The
navgraph is an agentic sitemap: it shows where the agent/user is, where they can
go, which surface is active, which path has been traversed, and which
capabilities are available at each reachable location.

The navgraph is derived from manifest topology, product runtime state, and
projection navigation. It is not necessarily the product graph. A product graph
can contain internal execution, recovery, policy, or persistence states that are
not useful navigation locations. A RouteDeck navgraph can also add
product-facing orientation nodes that summarize several product graph states.

Navgraph answers the location question. Capability answers the action question.

```text
Navgraph: where can the agent/user be?
Capability contract: what can the agent/user do there?
Projection: what is true right now?
Surface: what UI is presented now?
Dispatch: how does a requested change become validated state?
```

Example product-facing navgraph:

```json
{
  "current": {"node_id": "detail", "surface_id": "detail.product_detail"},
  "nodes": [
    {"id": "browse", "label": "Browse products"},
    {"id": "detail", "label": "Product detail"},
    {"id": "cart", "label": "Cart"}
  ],
  "edges": [
    {"from": "browse", "to": "detail", "action_id": "catalog.open"},
    {"from": "detail", "to": "cart", "action_id": "cart.add_item"}
  ],
  "traversed": ["browse", "detail"],
  "reachable": ["browse", "cart"]
}
```

### Capability

A modality-neutral product ability exposed by the runtime. Capabilities are the
shared semantic layer for surfaces, chat, automation, and diagnostics. A
capability groups the product intent, the operations that execute it, the
entities that bind it, and the surfaces that present it.

`capability_id` connects manifest nodes and action specs to a shared ability.
Runtime operations are the currently legal executable instances of that ability.

Example capability contract:

```json
{
  "capability_id": "cart.add_item",
  "label": "Add item to cart",
  "operation_ids": ["variant.select", "cart.add_item"],
  "entity_kinds": ["variant"],
  "surface_ids": ["detail.product_detail"],
  "chat_enabled": true,
  "surface_enabled": true
}
```

Capabilities attach to navgraph nodes and edges. A node can advertise the
capabilities available at that location. An edge can record the operation that
traverses from one location to another. The same capability remains available to
surfaces and chat when the current navgraph location allows it.

### Operation

A typed runtime action represented by `RouteDeckOperation`. Operations are what
a product UI, product agent, automation, or diagnostic client asks the runtime
to dispatch. Operation metadata includes label, input schema, invocation kind,
dispatch readiness, required and missing args, safety class, execution mode,
guard text, target node, and surface id.

### Legal Operation

An operation the graph/runtime policy allows from the current state. A legal
operation is not automatically a button. Clients still respect
`can_dispatch_now`, `invocation_kind`, `required_args`, `missing_args`,
`execution_mode`, and safety class.

### Product Operation

A product-facing operation such as `catalog.open` or `cart.add_item`. Product
operations describe user or business intent in product language. Product
operations have one of these outcomes: keep the current RouteDeck/navgraph node,
transition to another RouteDeck/navgraph node, update a projected surface,
commit a side effect, stage a review, or return a guarded rejection.

### Surface Intent

A product-agent or product-planner request to show one of the currently valid
product surfaces. Surface intent is product language over RouteDeck surface
options. Product agents choose a valid `surface_id` from planning context; they
do not expose or invoke `route.switch_surface` as ordinary product vocabulary.

Example:

```json
{"intent": "open_surface", "surface_intent": {"surface_id": "detail.product_detail"}}
```

### Available Entity

A product-owned entity exposed by the current product context, such as a
product, variant, cart item, policy candidate, or execution trace. Available
entities are the common entity pool for chat and surfaces. They carry stable
`entity_key` values and server-bindable operation arguments for the product
runtime. They do not expose private upstream identifiers, secrets, or raw
framework diagnostics in ordinary product UI or chat text.

Identifier rule:

- label: human and agent-readable text, such as `Medusa T-Shirt`.
- entity key: stable context-local binding key, such as `product:medusa-shirt`.
- opaque ref: runtime dispatch argument, such as `product_opaque_1`.

### Rendered Entity

An available entity currently shown by one or more surfaces. Rendered entities
are the subset a user can click, select, or inspect visually. Chat access is not
limited to rendered entities; chat uses all available entities in the current
planning context.

### Selectable Entity

A selected available entity that fills an operation argument. Selectable
entities bind user language or surface events to typed operation arguments
without inventing hidden ids or using a deterministic command router.

Example:

```json
{
  "kind": "variant",
  "entity_key": "variant:s-black",
  "label": "S / Black",
  "parent_label": "Medusa T-Shirt",
  "rendered_on": ["detail.product_detail"],
  "operations": [
    {"operation_id": "variant.select", "args": {"variant_ref": "variant_opaque_1"}},
    {"operation_id": "cart.add_item", "args": {"variant_ref": "variant_opaque_1", "quantity": 1}}
  ]
}
```

### Planning Context

A product-owned view derived from RouteDeck projection and product state for a
product agent or product planner. Planning context includes only the context the
product exposes to the agent: current node, current surface, legal product
operations, valid surface options, available entities, surface affordances, and
missing arguments. RouteDeck defines projection terms; the product owns
prompt-ready summaries and entity-binding policy.

Planning context is not a RouteDeck core schema. It is a product adapter layer
that protects the product agent from guessing hidden ids while keeping private
upstream identifiers out of ordinary chat text.

Example product-owned shape:

```json
{
  "current": {"node_id": "detail", "surface_id": "detail.product_detail"},
  "legal_operations": [
    {"id": "cart.add_item", "label": "Add to cart", "required_args": ["variant_ref", "quantity"]}
  ],
  "surface_options": [
    {"surface_id": "detail.product_detail", "label": "Product details"}
  ],
  "available_entities": [
    {
      "entity_key": "variant:s-black",
      "kind": "variant",
      "label": "S / Black",
      "rendered_on": ["detail.product_detail"],
      "operations": [
        {"operation_id": "cart.add_item", "args": {"variant_ref": "variant_opaque_1", "quantity": 1}}
      ]
    }
  ],
  "surface_affordances": [
    {
      "surface_id": "detail.product_detail",
      "affordance_id": "add_to_cart",
      "operation_id": "cart.add_item",
      "entity_keys": ["variant:s-black"]
    }
  ]
}
```

## Surfaces

### Surface

An interactive projection represented by `RouteDeckSurface`. A surface wraps a
developer-authored or agent-generated component and receives sanitized props
from projection. A surface presents runtime capabilities through declared
affordances; it does not mutate graph state directly.

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
  "lifecycle": "stable",
  "props": {"product": {"title": "Medusa T-Shirt", "entity_key": "product:medusa-shirt"}}
}
```

### Surface Affordance

A declared interaction that a surface emits. An affordance connects a UI event
to a capability request, product operation, surface intent, or semantic
observation. It uses entity keys and event payload fields for binding; it does
not give the component authority to mutate graph state directly.

Reference shape:

```json
{
  "surface_id": "detail.product_detail",
  "affordance_id": "add_to_cart",
  "event": "add_clicked",
  "capability_id": "cart.add_item",
  "operation_id": "cart.add_item",
  "entity_key": "variant:s-black",
  "arg_bindings": {
    "variant_ref": {"from": "entity", "path": "operations.cart.add_item.args.variant_ref"},
    "quantity": {"from": "event", "path": "quantity"}
  }
}
```

Binding expressions use explicit `{from, path}` objects. `from: "entity"` reads
from the current available entity identified by `entity_key`. `from: "event"`
reads from the surface event payload. The product runtime resolves bindings and
then dispatches.

### Generated Surface

A surface whose component specification is produced by an agent or another
generator. Generated surfaces follow the same rules as developer-authored
surfaces: sanitized props down, declared affordances up, runtime dispatch for
semantic effects, and semantic observations back to agent context.

## Interaction Flows

### Surface Interaction Event

A structured event emitted by a surface when the user performs a semantic
interaction. It contains the `surface_id`, `affordance_id`, optional
`entity_key`, and event payload. It does not contain private upstream ids.

Example:

```json
{
  "surface_id": "detail.product_detail",
  "affordance_id": "add_to_cart",
  "entity_key": "variant:s-black",
  "payload": {"quantity": 1}
}
```

Surface flow:

```text
component emits surface interaction event
  -> product runtime resolves capability and entity binding
  -> RouteDeck dispatch validates operation and args
  -> graph commits, rejects, blocks, or opens review
  -> RouteDeck emits events and next projection
  -> product agent receives semantic observation when relevant
```

### Chat Capability Request

A product-agent request to invoke a capability from natural language. Chat uses
the same planning context as surfaces. The agent selects an operation,
`entity_key`, surface intent, or clarification. The product runtime resolves the
request to dispatch args and validates it the same way it validates a surface
interaction.

Example:

```json
{"operation_id": "cart.add_item", "entity_key": "variant:s-black", "quantity": 1}
```

Both this chat request and the surface event above resolve server-side to:

```json
{"operation_id": "cart.add_item", "args": {"variant_ref": "variant_opaque_1", "quantity": 1}}
```

Text matching is a fallback for natural-language chat. It matches only against
the current available-entity index, returns a guard or clarification on
ambiguity, and never scans private product data or invents refs.

### Semantic Observation

A product-owned summary of a state-relevant interaction or runtime result for
agent context. Semantic observations are not raw UI logs. They describe what
matters for future planning.

Examples:

```json
{"type": "entity_selected", "summary": "User selected S / Black.", "entity_key": "variant:s-black"}
```

```json
{"type": "operation_result", "operation_id": "cart.add_item", "accepted": true, "summary": "Added S / Black to cart."}
```

### Agent Context Update

The product-owned process that records semantic observations, user messages,
planning context, and runtime results into the next agent turn. Agent context
does not store raw surface events, hidden route operations, private refs, or
diagnostic traces unless the product is explicitly in a developer/diagnostic
surface.

## Topology And Runtime

### Manifest

The static RouteDeck contract for the product-facing navgraph and capability
surface. `RouteDeckManifest` declares possible nodes, edges, action specs,
policies, and test paths. It is capability and topology shape, not live state.

Minimal manifest shape:

```json
{
  "version": "medusa-agent-slice3",
  "nodes": [{"id": "detail", "label": "Product Detail", "capability_id": "catalog.detail"}],
  "edges": [{"from_stage": "browse", "to_stage": "detail", "type": "action", "action_id": "catalog.open"}],
  "actions": [{"id": "catalog.open", "label": "View product", "capability_id": "catalog.detail"}]
}
```

### Node

A navgraph location declared as `RouteDeckNodeSpec`. A node represents a
product-facing place the agent/user can occupy: workflow, section, detail, or
transient state. Nodes declare allowed actions and allowed/default surfaces. A
RouteDeck node does not need to map one-to-one to a product graph node.

### Edge

A navgraph route declared as `RouteDeckEdgeSpec`. Edges describe navigation or
workflow transitions between RouteDeck nodes. Actions are not navgraph nodes. When
a product action triggers a navgraph transition, the edge records that action in
`action_id`; the action remains operation vocabulary and the edge remains
navgraph topology.

Concrete rule: `catalog.open` is dispatched as an operation. The navgraph edge
`browse -> detail` records `action_id: "catalog.open"` so debuggers and tests can
explain why the transition exists. UI code must not render `catalog.open` as a
node in the navgraph.

### Action Spec

The static manifest declaration for an operation, represented by
`RouteDeckActionSpec`. An action spec says an action belongs to the product
contract. Runtime operation metadata says the action is currently legal or
available in the current projection.

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

### Runtime State

The current graph-backed RouteDeck state, represented by `RouteDeckRuntimeState`.
It includes the current `RouteDeckProjection`, runtime status, graph state, last
event, diagnostics, and metadata.

### Dispatch

The generic operation submission path. Clients send a `RouteDeckDispatchInput`
and receive a `RouteDeckDispatchResult`. Dispatch validates setup, guards,
required args, safety policy, and graph state before accepting or rejecting the
operation.

Example guarded result:

```json
{
  "operation_id": "cart.add_item",
  "accepted": false,
  "messages": [{"content": "Choose a variant and quantity before adding an item to cart."}],
  "events": [{"event_type": "guard_failure", "payload": {"message": "Choose a variant first."}}]
}
```

### Navigation State

The projected browser/runtime location represented by `RouteDeckNavigationState`
and `RouteDeckLocation`. It tracks current RouteDeck node/surface params, back
stack, forward stack, and whether back/forward/cancel are legal.

Example:

```json
{
  "current": {"node_id": "detail", "surface_id": "detail.product_detail"},
  "back_stack": [{"node_id": "browse", "surface_id": "browse.product_list"}],
  "forward_stack": [],
  "can_back": true,
  "can_forward": false,
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

### Product Agent

The product-owned LLM, planner, or assistant that consumes product planning
context derived from RouteDeck projection. RouteDeck does not own product
prompts, model calls, LLM behavior, domain wording, or deterministic phrase
routing.

### Product Boundary

RouteDeck owns the reusable state, projection, navigation, navgraph, capability
contract, dispatch, surface, diagnostics, introspection, and client-store
contracts. Products own domain vocabulary, prompts, planning-context
construction, product agents, product runtimes, domain data, auth, persistence,
business policy, product routes, product UI copy, LLM calls, semantic
observation policy, and domain side effects.
