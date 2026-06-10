# RouteDeck Reference

Status: canonical framework reference
Date: 2026-06-06

Schema authority: `routedeck_core/models.py`

This file is the north-star reference for RouteDeck framework language,
ownership boundaries, capability semantics, and payload shapes. Product examples
define their own domain vocabulary. RouteDeck framework terms follow this file
and the schema names in `routedeck_core/models.py`.

This document is the software-on-paper contract for RouteDeck. A downstream
implementation is correct only when a reviewer can trace every visible behavior,
stream event, URL update, surface affordance, action chip, dispatch, diagnostic
payload, and agent planning input back to this reference.

The reference intentionally describes contracts, schemas, protocols, and
boundaries instead of implementation code. Product examples demonstrate adoption;
they do not redefine RouteDeck.

## Authority Order

1. `routedeck_core/models.py` defines enforceable schema names and fields.
2. This file defines framework meaning, ownership, and usage.
3. `docs/agentic-ui-state-runtime.md` explains the architecture direction.
4. Product specs, plans, and examples apply these terms inside product
   boundaries.

When product docs, product code, React helpers, tests, or examples conflict with
this file, update the downstream artifact or make a deliberate framework
decision here first. Do not treat drift in `examples/medusa-agent`,
SaaStoAgent/Corpus, or React client code as new RouteDeck law.

## Reference-App Reset Rule

The Medusa reference app exists to prove RouteDeck by starting from a normal
product agent and then adding RouteDeck contracts in disciplined slices. The
current proof target is barebones app-owned agent chat:

- one chat-first screen
- one product-owned agent streaming endpoint
- true Server-Sent Events for assistant text
- process-local conversation state
- no RouteDeck runtime, manifest, projection, dispatch, inspect, navgraph,
  product surface, commerce surface, cart mutation, Store API behavior,
  diagnostics panel, graph-first placeholder, or RouteDeck-prefixed public API

The runnable Medusa example must be stripped back to that chat-only proof before
new RouteDeck behavior is added again. Later RouteDeck slices are valid only
when each slice adds one contract from this document and proves that contract
through product-owned routes and normal chat.

The barebones Medusa app is a product example, not a RouteDeck framework API. It
does not prove RouteDeck by showing many framework widgets. It proves RouteDeck
by showing that RouteDeck can be introduced into a real product agent without
absorbing the product agent.

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
legal operations, surfaces, presentation state, navigation state, navgraph, and
diagnostics.
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
  "navigation": {
    "current": {
      "node_id": "detail",
      "surface_id": "detail.product_detail",
      "deeplink": {"url": "/shop/detail/product-public-123", "resumable": true}
    }
  }
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
navgraph is a graph: nodes are product-facing locations and edges are reachable
routes between those locations. A visual surface that presents a navgraph must
show that topology as a graph, not only as a flat list of labels. The navgraph
shows where the agent/user is, where they can go, which surface is active, which
path has been traversed, which locations can be opened directly, and which
capabilities are available at each reachable location.

The navgraph is derived from manifest topology, product runtime state, and
projection navigation. It is not necessarily the product graph. A product graph
can contain internal execution, recovery, policy, or persistence states that are
not useful navigation locations. A RouteDeck navgraph can also add
product-facing orientation nodes that summarize several product graph states.

Visual navgraph surfaces are read-only orientation and inspection surfaces. A
user selecting a navgraph node can update a local inspector selection, but it
must not dispatch, navigate, mutate graph state, or change the browser URL.
Deeplinks remain copyable address-bar state owned by the product URL codec; a
navgraph node's deeplink is data for inspection and resume, not an `href` for
the graph canvas.

Action chips are separate product controls derived from product-curated
capabilities, operations, affordances, or agent proposals. They are not
navgraph nodes, and they are not rendered by making graph nodes clickable.
Internal `route.*` operations remain framework plumbing and must not appear as
ordinary product action chips.

Action chips belong to the product chat or assistant experience. They must be
presented as product-agent suggestions, next-best actions, or composer-adjacent
controls, not as navgraph controls, graph-node actions, edge labels, or
inspector controls. In the SaaStoAgent Corpus pattern, quick actions are
attached to the latest assistant turn or active composer context while
RouteDeck validates the operation behind the product-owned action endpoint. A
product can use a different visual style, but the control still belongs with
the product agent experience, not with the navgraph canvas or inspector.

Concrete implementation rule: a product shell can derive chat action chips from
projected capabilities, legal operations, surface affordances, rendered
entities, or product-agent proposals, then filter them through product safety
policy and RouteDeck readiness. The same action must be representable through
chat planning context. The navgraph can expose related action metadata for
inspection, but it must not be the source or rendering location for product
action chips.

`legal_operations` is a policy/runtime fact, not a command to render every
operation as a visible chip. Product shells should suppress hidden operations,
blocked operations, unbound selector/form operations, and normal same-node
operations such as "browse products" while the current node is already
`browse`. Show same-node operations only when the product deliberately labels
them as refresh/reload controls and they remain available through chat.

Product surfaces and navgraph/inspector surfaces must be structurally separate
in the UI. In agent-centric products, the active product surface normally lives
inside the chat or workbench stream, not as a detached product side panel. A
product card, variant picker, cart button, or home CTA emits a declared surface
affordance. The navgraph displays topology and local inspector focus only. If a
product click changes the visible graph, that graph change is a consequence of
product dispatch returning a new projection, not the click directly mutating the
navgraph.

State details such as reachable nodes, legal operations, capabilities,
available entities, rendered entities, surface affordances, and edge action
metadata belong in a read-only inspector or diagnostics layer. They should not
be packed into the graph canvas when doing so makes the topology harder to
read.

When a product has a natural agent starting point, the product should expose a
stable home or root navgraph node. That node orients new sessions and gives the
layout a stable center without pretending to be the entire product graph.

Navgraph answers the location question. Capability answers the action question.

```text
Navgraph: where can the agent/user be?
Capability contract: what can the agent/user do there?
Deeplink: what browser URL opens or resumes a location?
Projection: what is true right now?
Surface: what UI is presented now?
Dispatch: how does a requested change become validated state?
```

Example product-facing navgraph:

```json
{
  "current": {
    "node_id": "detail",
    "surface_id": "detail.product_detail",
    "deeplink": {"url": "/shop/detail/product-public-123", "resumable": true}
  },
  "nodes": [
    {"id": "browse", "label": "Browse products", "deeplink": {"url": "/shop/browse", "resumable": true}},
    {"id": "detail", "label": "Product detail", "deeplink": {"url": "/shop/detail/product-public-123", "resumable": true}},
    {"id": "cart", "label": "Cart", "deeplink": {"url": "/shop/cart", "resumable": true, "requires_auth": false}}
  ],
  "edges": [
    {"from": "browse", "to": "detail", "action_id": "catalog.open"},
    {"from": "detail", "to": "cart", "action_id": "cart.add_item"}
  ],
  "traversed": ["browse", "detail"],
  "reachable": ["browse", "cart"]
}
```

### Deeplink

A copyable browser URL for a RouteDeck location. Deeplinks are visible in the
address bar and can be pasted into a new tab or shared so the product can resume
the same agent state when auth and policy allow it.

`RouteDeckDeepLink` has this shape:

```json
{"url": "/shop/detail/product-public-123", "resumable": true, "requires_auth": false, "label": "Product detail"}
```

Rules:

- RouteDeck defines the deeplink fields on `RouteDeckLocation` and
  `RouteDeckNavGraphNode`.
- Products own the URL format, route parsing, auth checks, tenancy checks, and
  state restoration.
- Browser-facing deeplinks are product-owned URL codecs. The Corpus pattern is
  the reference consumption model: graph location lives in product path segments
  such as `/app/home` or `/app/agents/:agent_id/:node_id`, while query
  parameters carry optional surface/presentation state such as `surface_id`.
  New product examples should not make framework-looking query keys such as
  `?rd_node=...` the canonical public URL for graph location. Products can
  accept and normalize legacy query links in their decoder.
- A deeplink URL must be safe to show in the browser address bar. It must not
  expose private database IDs, secret refs, dispatch payloads, or diagnostic
  traces.
- If a URL requires auth, the deeplink still points to the intended location,
  and the product chooses one guarded outcome: restore through sign-in, show an
  access guard, or reject the resume.
- When the current RouteDeck location changes, the browser URL should track the
  current location's deeplink with `pushState` or `replaceState`.
- A visual navgraph must not use node deeplinks as clickable graph navigation.
  Deeplinks are copied from the address bar or decoded from pasted browser URLs,
  while graph-node selection stays read-only.
- When the user pastes or navigates to a deeplink, the product should decode it
  into a RouteDeck location and ask the runtime to open that location through
  the normal guarded navigation path, usually `route.open_node`.
- The current surface and the chat agent must converge on the same restored
  state. Anything reachable through a surface deeplink must also be reachable
  through chat if the same user and auth state allow it.
- Convergence is observable behavior, not just schema parity. If public chat says
  it opened, browsed, selected, compared, or changed a product surface, the
  product must apply an accepted runtime dispatch, state event, or explicit
  projection refresh so surfaces, URL path state, planning context, and debug
  context agree. Assistant prose without a matching projection/runtime update is
  drift.
- That convergence must be session-consistent: conversation id, product agent
  thread id, projection/session state, accepted dispatch or surface intent,
  route/state stream events, debug/inspect context, and projection version refer
  to the same product runtime session.

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

Planning context is also the grounding boundary for public chat. Product facts
that affect user decisions, such as names, prices, variants, colors, sizes,
availability, cart contents, and current surface state, must come from current
projection/planning context or a product tool result. If the product has not
provided that context, the agent asks for the missing setup or says it cannot
verify the fact yet.

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
RouteDeck node does not need to map one-to-one to a product graph node. Runtime
navgraph nodes can include a `deeplink` so the location can be opened from the
browser address bar when the product allows it.

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

Runtime interface contract:

| Operation | Input | Output | Meaning |
| --- | --- | --- | --- |
| snapshot | Product request context | `RouteDeckRuntimeState` | Return current graph-backed RouteDeck state. |
| projection | Product request context | `RouteDeckProjection` | Return the client-facing projection only. |
| dispatch | `RouteDeckDispatchInput` and product request context | `RouteDeckDispatchResult` | Validate and apply or reject one semantic request. |
| inspect | Product query and request context | `RouteDeckIntrospection` | Explain current state without changing it. |
| stream | Product request context | `RouteDeckEvent` sequence | Emit RouteDeck state events, not product-agent text. |

The interface contract is transport-neutral. A product can expose it through
product-owned HTTP routes, a generic RouteDeck API plane, an in-process adapter,
or test fixtures. The contract does not grant RouteDeck ownership of product
routes, product auth, product agents, or product side effects.

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
stack, forward stack, deeplink, and whether back/forward/cancel are legal.
`RouteDeckLocation.deeplink.url` is the current copyable browser URL when the
product can safely expose one.

Example:

```json
{
  "current": {
    "node_id": "detail",
    "surface_id": "detail.product_detail",
    "deeplink": {"url": "/shop/detail/product-public-123", "resumable": true}
  },
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
product runtime validation. React clients can use the RouteDeck history helpers
to mirror `RouteDeckLocation.deeplink.url` into the address bar and to decode
browser navigation back into guarded RouteDeck navigation requests.

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
Accepted dispatch events that change RouteDeck-visible state must carry either
`payload.state` or `payload.projection` so generic clients can apply the update
without product-specific navigation logic.
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
observation policy, URL/deeplink codecs, deeplink auth/resume policy, and domain
side effects.

## API Planes And Route Ownership

RouteDeck supports two API planes. A product chooses one or both, but it must not
mix product domain behavior into the framework namespace.

### Product-Owned API Plane

The product API plane exposes product behavior in product language. It is the
default for reference apps and app integrations.

Reference route families:

| Route family | Method | Purpose | RouteDeck meaning |
| --- | --- | --- | --- |
| `/api/<product>/state` | GET | Return product state plus RouteDeck projection. | Product-owned wrapper around snapshot/projection. |
| `/api/<product>/action` | POST | Dispatch one product operation or surface event. | Product-owned wrapper around dispatch. |
| `/api/<product>/agent/stream` | POST | Stream one product-agent chat turn. | Product-owned agent stream, not a RouteDeck stream. |
| `/api/<product>/inspect` | POST | Return read-only RouteDeck introspection for this product. | Product-owned diagnostics surface. |
| `/api/<product>/route-stream` | GET | Subscribe to RouteDeck state events for this product. | Product-owned wrapper around RouteDeck events. |

Product-owned routes can include Medusa, Corpus, SaaStoAgent, or any domain
namespace because the product owns the domain route. Those routes must return
RouteDeck-derived payloads only after product auth, tenancy, and data policy are
applied.

### Generic RouteDeck API Plane

The generic RouteDeck API plane exposes reusable framework contracts. It is
valid for framework deployments, devtools, local examples, and product-neutral
services.

Reference route families:

| Route family | Method | Purpose | RouteDeck meaning |
| --- | --- | --- | --- |
| `/api/routedeck/manifest` | GET | Return `RouteDeckManifest`. | Static topology and capability contract. |
| `/api/routedeck/snapshot` | GET | Return `RouteDeckRuntimeState`. | Current graph-backed runtime state. |
| `/api/routedeck/projection` | GET | Return `RouteDeckProjection`. | Current client-facing projection. |
| `/api/routedeck/dispatch` | POST | Accept `RouteDeckDispatchInput`. | Generic dispatch contract. |
| `/api/routedeck/inspect` | POST | Return `RouteDeckIntrospection`. | Generic diagnostics contract. |
| `/api/routedeck/stream` | GET | Emit `RouteDeckEvent` frames. | Generic state/event stream. |

Generic RouteDeck routes must not include product-specific path segments. Do not
use `/api/routedeck/medusa`, `/api/routedeck/corpus`, or `/api/routedeck/cart`.
Do not use `/api/routedeck/checkout` or `/api/routedeck/admin`.

### Medusa Route Rule

The Medusa reference app uses product-owned routes only. The chat-only reset
target exposes `POST /api/medusa-agent/agent/stream` plus an optional health
route. It does not expose RouteDeck routes, RouteDeck-derived product endpoints,
Medusa Store API behavior, cart behavior, navgraph behavior, or inspector
behavior.

Future Medusa RouteDeck slices expose RouteDeck-derived product contracts under
`/api/medusa-agent/*`. No public Medusa endpoint is served under
`/api/routedeck/*`.

## Deeplink And Browser URL Contract

Browser URL state is a product-owned codec over `RouteDeckLocation`. RouteDeck
defines location and deeplink fields. The product defines the address grammar,
decoding, authorization, normalization, and browser history policy.

### Canonical URL Shape

Graph location belongs in product path segments. Optional surface, presentation,
or resumable view state belongs in query parameters.

Reference examples:

| Product | Canonical path | Query state | Meaning |
| --- | --- | --- | --- |
| Corpus home | `/app/home` | none | Home RouteDeck node. |
| Corpus agent work | `/app/agents/agent-public-123/learning` | `surface_id=learning.policy_gaps` | Agent-scoped node with active surface. |
| Medusa home | `/` | none | Buyer-agent home node. |
| Medusa browse | `/browse` | none | Product browsing node. |
| Medusa detail | `/detail/t-shirt` | `surface_id=detail.product_detail` | Product detail node for a public product handle. |
| Medusa cart | `/cart` | none | Cart node. |

The path selects the RouteDeck location. The query refines state inside that
location. New examples must not make `?rd_node=detail` or `?node_id=detail` the
canonical browser URL for graph location. Products can decode legacy query links
and immediately normalize them to path-shaped deeplinks.

### URL State Rules

- `RouteDeckLocation.node_id` maps to product path semantics.
- `RouteDeckLocation.surface_id` maps to `surface_id` query state unless the
  product has a stronger path grammar for surface identity.
- `RouteDeckLocation.params` contains product-owned public parameters such as
  public agent id, public product handle, public workspace slug, selected tab,
  view mode, or draft handle.
- Query parameters carry optional presentation state, active surface state,
  tab/view state, and legacy compatibility state.
- Query parameters must not carry private database ids, operation args,
  dispatch payloads, secret refs, payment ids, private cart ids, internal graph
  state, or diagnostic traces.
- A browser URL copied from the address bar must be safe for a user to paste
  into a new tab or send to another authorized user.
- Browser replay asks the runtime to open a location. It is not product intent
  and it is not equivalent to clicking a product action.

### Decode And Normalize Flow

Browser replay follows this contract:

```text
browser URL
  -> product URL codec
  -> RouteDeckLocation candidate
  -> product auth and tenancy checks
  -> guarded route operation or direct runtime location open
  -> RouteDeck projection
  -> normalized address-bar deeplink
```

The normalized address bar must track `RouteDeckLocation.deeplink.url` after a
successful location commit. Invalid URLs produce a product-owned guard, redirect,
or recovery projection. Unknown query parameters are ignored unless the product
explicitly whitelists them.

### Navgraph Selection Is Not Browser Navigation

A visual navgraph node can be selected for local inspection. That local
selection is not a browser URL update, not a runtime dispatch, not a state
commit, and not a deeplink replay. The navgraph can show a node's deeplink as
copyable metadata. It must not render the node as an anchor or treat graph
selection as user intent.

## Server-Sent Events Contract

RouteDeck products normally have three stream lanes. They share the SSE frame
format, but they do not share ownership.

| Lane | Endpoint owner | Typical route | Primary event family | Meaning |
| --- | --- | --- | --- | --- |
| Product-agent chat stream | Product | `POST /api/<product>/agent/stream` | `message_delta` | One conversational turn. |
| RouteDeck state stream | RouteDeck contract through product or generic API | `GET /api/<product>/route-stream` or `GET /api/routedeck/stream` | `projection_update` | State/projection subscription. |
| Diagnostics stream | Product or devtools | `GET /api/diagnostics/stream` or `POST /api/<product>/inspect` plus stream wrapper | `diagnostic_event` | Read-only introspection. |

### SSE Frame Rules

- Response content type is `text/event-stream`.
- Every event frame uses `event: <name>` and `data: <json payload>`.
- Keepalive comments use `: ping` and do not carry semantic state.
- Product-agent streams must not emit private ids, hidden route operations,
  dispatch traces, auth headers, payment ids, admin credentials, or raw graph
  state in public chat frames.
- RouteDeck state streams emit `RouteDeckEvent` payloads and include
  `projection` or `state` when clients need to apply a projection update.
- Diagnostics streams are read-only and can expose framework internals only
  inside diagnostic contexts.
- The stream producer owns event ordering. Clients apply events in order and
  ignore event names they do not understand.
- A stream end event closes semantic work. Network close without stream end is
  treated as interrupted, not successful.

### Product-Agent Chat SSE

The product-agent chat stream is product-owned. It streams assistant text and
product-safe semantic observations. It can carry RouteDeck event summaries only
when the product intentionally bridges dispatch results into the same turn.

Reference request schema:

```json
{
  "message": "show me products",
  "conversation_id": "conversation-public-1",
  "session_id": "session-public-1"
}
```

Reference event sequence:

```text
event: stream_start
data: {"conversation_id":"conversation-public-1","model":"gpt-5-mini"}

event: agent_start
data: {"agent_name":"medusa-commerce-agent"}

event: message_delta
data: {"content":"I can help you browse demo products."}

event: semantic_observation
data: {"type":"assistant_response","summary":"Assistant offered shopping help."}

event: agent_end
data: {}

event: stream_end
data: {}
```

Reference error event:

```text
event: error
data: {"code":"openai_api_key_missing","message":"The shopping assistant is not configured."}
```

Chat stream rules:

- `conversation_id` is product-owned conversation identity.
- If a LangGraph-backed product agent is used, `conversation_id` maps to the
  graph thread identity through the product adapter.
- The product agent reads planning context before choosing a product operation,
  surface intent, answer, or clarification.
- `message_delta` streams assistant text incrementally from the agent runtime.
- Splitting a completed response into fake deltas is not a valid proof of
  streaming.
- Missing model credentials produce an error event. A fake deterministic
  fallback assistant is not a valid product-agent proof.
- A chat turn that dispatches a product operation reports the user-facing result
  in product language. It does not dump RouteDeck internals into the transcript.

### RouteDeck State SSE

The RouteDeck state stream emits `RouteDeckEvent` frames. It is for projection
updates, runtime status, guard failures, operation lifecycle, and surface
updates. It is not an assistant text stream.

Reference event schema:

```json
{
  "event_type": "projection_update",
  "turn_id": "turn-public-1",
  "projection_version": 9,
  "payload": {
    "projection": {"projection_version": 9},
    "state": {"status": "idle"}
  }
}
```

State stream rules:

- `projection_update` carries a `projection` payload or a full `state` payload.
- `operation_started` identifies the operation and projection version at start.
- `operation_completed` identifies the operation and carries the next state or
  projection.
- `guard_failure` carries a product-safe guard message and diagnostic metadata
  only when the stream is diagnostic or authenticated for that detail.
- `surface_update` carries changed surface ids and next projection details.
- `runtime_status` carries status changes such as `refreshing`, `streaming`,
  `dispatching`, `recovering`, or `failed`.

### Diagnostics SSE

Diagnostics streams carry introspection snapshots. They are read-only. A
diagnostics stream must never become the default product UI, a public chat
answer, a product action chip source, or a substitute for the product runtime.

Reference event schema:

```json
{
  "event_type": "diagnostic_event",
  "turn_id": "turn-public-1",
  "projection_version": 9,
  "snapshot": {
    "graph_manifest": {},
    "runtime_snapshot": {},
    "introspection": {},
    "projection": {}
  }
}
```

## Planning Context Contract

Planning context is product-owned, but RouteDeck defines the source facts and
the filtering rules. Corpus is the proven consumption pattern. RouteDeck now
treats these reusable rules as part of the framework reference.

### Planning Context Inputs

Planning context is derived from:

- `RouteDeckProjection.current_context`
- `RouteDeckProjection.graph_node`
- `RouteDeckProjection.navigation.current`
- active `RouteDeckSurface` summaries
- legal product operations
- valid surface options
- available entities
- rendered or selectable entities
- surface affordances
- missing arguments and readiness metadata
- product auth, tenancy, and safety filters

Planning context excludes:

- hidden `route.*` operations
- blocked operations
- private upstream ids
- secret refs
- raw graph state
- diagnostic traces
- endpoint paths
- dispatch payloads not already bound by policy
- product data outside the current authorized context

Reference planning context schema:

```json
{
  "current": {"node_id": "detail", "surface_id": "detail.product_detail"},
  "active_surface": {
    "surface_id": "detail.product_detail",
    "label": "Product details",
    "component": "MedusaProductDetail",
    "variant": "product_detail",
    "surface_kind": "peer",
    "description": "Inspect the selected product and choose a variant."
  },
  "surface_options": [
    {"surface_id": "detail.product_detail", "label": "Product details", "surface_kind": "peer"}
  ],
  "visible_entities": [
    {
      "entity_key": "variant:s-black",
      "label": "S / Black",
      "operation_id": "cart.add_item",
      "args": {"variant_ref": "variant_opaque_1", "quantity": 1}
    }
  ],
  "legal_operations": [
    {
      "id": "cart.add_item",
      "label": "Add to cart",
      "invocation_kind": "entity_selector",
      "can_dispatch_now": true,
      "required_args": ["variant_ref", "quantity"],
      "missing_args": [],
      "accepted_arg_keys": ["variant_ref", "quantity"],
      "execution_mode": "auto",
      "safety_class": "write_external"
    }
  ]
}
```

### Product-Agent Plan Schema

A product agent returns one of these intents:

| Intent | Required fields | Meaning |
| --- | --- | --- |
| `reply_now` | `message` | Answer without dispatch. |
| `clarify` | `message` | Ask for missing or ambiguous product information. |
| `open_surface` | `surface_intent.surface_id` or a legal surface operation | Ask runtime to show a valid product surface. |
| `propose_operation` | `operation_id`, optional `args` | Ask runtime to dispatch or stage one product operation. |
| `deep_work` | `message` plus product-specific metadata | Continue a product-owned longer task without bypassing runtime validation. |

Reference product-agent plan schema:

```json
{
  "intent": "propose_operation",
  "message": "I can add the selected size to your cart.",
  "operation_id": "cart.add_item",
  "args": {"variant_ref": "variant_opaque_1", "quantity": 1},
  "surface_intent": {},
  "confidence": 0.82,
  "preamble": "I found the selected variant."
}
```

Normalization rules:

- Unknown intent becomes `clarify`.
- Unknown operation id becomes `clarify`.
- Operations not present in product-facing legal operations become `clarify`.
- Args outside `accepted_arg_keys` are dropped before dispatch.
- Surface intents whose `surface_id` is absent from `surface_options` become
  `clarify`.
- Ambiguous visible entities produce clarification instead of guessed args.
- Product agents do not invent private refs. They bind only visible or available
  entity keys exposed through the current planning context.

## Action Chip Contract

Action chips are product UI controls. RouteDeck provides source facts and
readiness metadata. The product chooses what to render.

Render a product action chip only when all of these are true:

- the operation is product-facing
- `invocation_kind` is `direct` or a product-labeled surface action
- `can_dispatch_now` is true
- `execution_mode` is not `blocked`
- `missing_args` is empty
- the operation is not hidden
- the operation id does not start with `route.`
- the operation is not a normal current-node no-op
- product safety policy allows a visible suggestion
- the same action is available through chat planning context

Do not render a product action chip when any of these are true:

- the operation is `route.open_node`, `route.switch_surface`, `route.back`,
  `route.forward`, or `route.cancel`
- the operation exists only for browser replay
- the operation requires a form that is not open
- the operation requires a selected entity that is not selected
- the operation is blocked, hidden, diagnostic, recovery-only, or admin-only in
  the current public context
- the chip would duplicate the current location as a fake next action
- the chip would expose operation ids, endpoint paths, private ids, or framework
  vocabulary to ordinary users

Action chips attach to the product-agent experience: starter assistant turn,
latest assistant turn, composer-adjacent controls, or product-owned workbench
context. They do not attach to navgraph nodes, graph edges, inspector rows, or
diagnostic payloads.

## Surface Placement Contract

RouteDeck surfaces represent graph-projected product views. Placement is a
product UI decision, but the following boundaries are framework-level rules:

- active product surfaces belong in the product work area
- agent-centric products place active product surfaces in the chat/workbench
  stream when chat is the main experience
- navgraph and inspector surfaces are separate from product surfaces
- product clicks emit surface interaction events
- navgraph selections update local inspection focus only
- a product surface cannot become graph truth
- component local state cannot become graph truth
- semantic surface state graduates through product runtime validation

The Medusa buyer-agent reference uses a chat stream as the work area. Product
cards, variant controls, cart summaries, and home CTAs belong inside that
chat/workbench stream after RouteDeck is intentionally introduced. They are not
a detached side panel and they are not navgraph controls.

The barebones Medusa reset contains no RouteDeck product surface. It contains
only chat.

## Surface Event Contract

Surface events carry semantic UI intent from a rendered component to the product
runtime. They do not carry private refs or commit authority.

Reference surface event schema:

```json
{
  "surface_id": "detail.product_detail",
  "affordance_id": "add_variant_to_cart",
  "entity_key": "variant:s-black",
  "payload": {"quantity": 1}
}
```

Resolution contract:

```text
surface event
  -> find declared `RouteDeckSurfaceAffordance`
  -> resolve entity binding through `RouteDeckAvailableEntity`
  -> build `RouteDeckDispatchInput`
  -> validate operation readiness and args
  -> product runtime commits, rejects, blocks, or stages review
  -> return `RouteDeckDispatchResult`
  -> emit semantic observation and next projection
```

If the surface event does not match a declared affordance, the product runtime
rejects it. If the entity key is unknown, stale, unauthorized, or ambiguous, the
product runtime rejects or clarifies. If the event payload lacks required fields,
the product runtime returns a guard or form/review surface.

## Dispatch Contract

Dispatch is the only semantic mutation boundary RouteDeck defines. It accepts a
typed operation or surface event and returns a result.

Reference dispatch input schema:

```json
{
  "operation_id": "cart.add_item",
  "surface_event": null,
  "args": {"variant_ref": "variant_opaque_1", "quantity": 1},
  "graph_state": {"node": "detail"},
  "projection_version": 8,
  "context": {"session_id": "session-public-1"}
}
```

Reference dispatch result schema:

```json
{
  "operation_id": "cart.add_item",
  "accepted": true,
  "state": {"status": "idle", "projection": {"projection_version": 9}},
  "active_surface": {"surface_id": "cart.summary", "component": "MedusaCartSummary"},
  "messages": [{"content": "Added S / Black to cart."}],
  "events": [
    {
      "event_type": "operation_completed",
      "projection_version": 9,
      "payload": {"operation_id": "cart.add_item", "projection": {"projection_version": 9}}
    }
  ],
  "metadata": {"replace_path": "/cart"}
}
```

Dispatch rules:

- Dispatch validates projection version when supplied.
- Dispatch checks operation legality against current graph state.
- Dispatch validates required args, missing args, accepted arg keys, invocation
  kind, safety class, execution mode, auth, tenancy, and product policy.
- Dispatch resolves surface events before committing.
- Dispatch returns `accepted: false` with guard messages when it rejects.
- Dispatch returns the next RouteDeck state on every accepted mutation.
- Accepted dispatch events that change RouteDeck-visible state carry `state` or
  `projection` in the event payload.
- Dispatch does not call product side-effect APIs directly from the client.
  Product side effects happen inside the product runtime after validation.

## Diagnostics Contract

Diagnostics are explanation surfaces. They are not ordinary product UI and not
public chat.

Diagnostics can show:

- current node
- current surface
- reachable nodes
- legal operations
- blocked operations
- guard explanations
- surface projection
- navgraph topology
- route traces
- projection version
- runtime status
- sanitized graph state
- schema validation detail

Diagnostics must not:

- mutate graph state
- dispatch operations from a graph click
- become the default landing page
- replace product chat
- expose private ids in public chat
- render every operation as a product chip
- teach product agents to emit hidden `route.*` operations

## Schema Field Inventory

This inventory explains the schema authority without implementation code. Field
names and literal values come from `routedeck_core/models.py`.

### Manifest Schemas

`RouteDeckManifest`

| Field | Meaning |
| --- | --- |
| `version` | Product or framework contract version for this manifest. |
| `nodes` | Static `RouteDeckNodeSpec` declarations. |
| `edges` | Static `RouteDeckEdgeSpec` declarations. |
| `actions` | Static `RouteDeckActionSpec` declarations. |
| `capabilities` | Shared capability declarations referenced by nodes/actions. |
| `policies` | Product-neutral policy metadata and product-owned policy handles. |
| `test_paths` | Contract paths for validation and examples. |

`RouteDeckNodeSpec`

| Field | Meaning |
| --- | --- |
| `id` | Product-facing RouteDeck navgraph node id. |
| `label` | Human-readable node label. |
| `lane` | Product-defined grouping or lane. |
| `description` | Product-facing explanation of the location. |
| `prompt_placeholder` | Optional prompt hint for product UI. |
| `allowed_actions` | Action ids declared as possible from this node. |
| `expected_input` | Product-facing hint for expected user input. |
| `recovery_prompt` | Product-facing recovery copy. |
| `parent` | Optional parent node id for hierarchy. |
| `node_kind` | `workflow`, `section`, `detail`, or `transient`. |
| `capability_id` | Capability represented by this node. |
| `show_in_navgraph` | Whether this node appears in visual topology. |
| `show_in_capability_rail` | Whether this node contributes to capability presentation. |
| `cancel_target_node` | Guarded cancel destination. |
| `dirty_policy` | `none`, `confirm`, or `block` when leaving dirty state. |
| `allowed_surfaces` | Surface ids allowed by role or slot. |
| `default_surfaces` | Default surface id by role or slot. |

`RouteDeckEdgeSpec`

| Field | Meaning |
| --- | --- |
| `from` | Source RouteDeck node id. |
| `to` | Target RouteDeck node id. |
| `type` | Product-defined edge type. |
| `condition` | Static condition label or policy key. |
| `explanation` | Human-readable route explanation. |
| `action_id` | Operation that traverses this edge. |
| `capability_id` | Capability associated with this edge. |

`RouteDeckActionSpec`

| Field | Meaning |
| --- | --- |
| `id` | Product operation id. |
| `label` | Product-facing action label. |
| `capability_id` | Shared capability id. |
| `description` | Product-facing description. |
| `emphasis` | `primary` or `secondary`. |
| `kind` | `button`, `chip`, `form`, `nav`, or `summary`. |
| `category` | Product/action family such as auth, setup, navigation, execution, feedback, learning, or deployment. |
| `placement` | Suggested placement such as next-best, rail, inline, or evidence. |
| `fields` | Static `RouteDeckFieldSpec` input fields. |
| `payload` | Static product-owned metadata. |
| `invocation_kind` | Runtime invocation style if statically known. |
| `allowed_nodes` | Node ids where the action is possible. |
| `visibility` | `contextual`, `persistent`, or `dynamic`. |
| `recovery_prompt` | Product-facing recovery text. |
| `sensitive` | Whether action metadata needs sensitive handling. |

### Runtime And Projection Schemas

`RouteDeckRuntimeState`

| Field | Meaning |
| --- | --- |
| `projection` | Current `RouteDeckProjection`. |
| `status` | `idle`, `refreshing`, `streaming`, `dispatching`, `recovering`, or `failed`. |
| `graph_state` | Product-owned sanitized graph state snapshot. |
| `location` | Product-owned normalized browser path when supplied. |
| `last_event` | Last `RouteDeckEvent`. |
| `diagnostics` | Sanitized runtime diagnostics. |
| `metadata` | Product/framework metadata. |

`RouteDeckProjection`

| Field | Meaning |
| --- | --- |
| `current_context` | Product-facing current context label. |
| `graph_node` | Current RouteDeck/navgraph node id. |
| `projection_version` | Monotonic projection version. |
| `legal_operations` | Runtime `RouteDeckOperation` list legal in current state. |
| `surfaces` | Named `RouteDeckSurface` map. |
| `presentation_state` | Product-owned resumable presentation/session state. |
| `navigation` | Current `RouteDeckNavigationState`. |
| `capabilities` | Current capability specs relevant to projection. |
| `navgraph` | Current visual/navgraph topology. |
| `available_entities` | Product entity pool for chat and surfaces. |
| `surface_affordances` | Declared surface event bindings. |
| `diagnostics` | Sanitized projection diagnostics. |

`RouteDeckOperation`

| Field | Meaning |
| --- | --- |
| `id` | Runtime operation id. |
| `label` | Product-facing label. |
| `description` | Product-facing description. |
| `category` | Product/action family. |
| `kind` | Presentation kind. |
| `placement` | Suggested product placement. |
| `emphasis` | `primary` or `secondary`. |
| `safety_class` | `navigation`, `state_selection`, `draft`, `read_external`, `write_external`, `destructive`, `credential`, or `admin`. |
| `execution_mode` | `auto`, `review`, or `blocked`. |
| `input_schema` | Product-owned input schema. |
| `payload` | Runtime metadata. |
| `invocation_kind` | `direct`, `form`, `entity_selector`, `surface`, or `hidden`. |
| `can_dispatch_now` | Whether direct dispatch is currently allowed. |
| `required_args` | Required argument keys. |
| `missing_args` | Required args not yet available. |
| `guard` | Product-safe guard or block reason. |
| `target_node` | RouteDeck node after success, when applicable. |
| `capability_id` | Shared capability id. |
| `surface_id` | Surface associated with the operation. |

### Navigation Schemas

`RouteDeckDeepLink`

| Field | Meaning |
| --- | --- |
| `url` | Product-owned copyable browser URL. |
| `resumable` | Whether the product can attempt resume. |
| `requires_auth` | Whether resume requires auth. |
| `label` | Optional human-readable deeplink label. |

`RouteDeckLocation`

| Field | Meaning |
| --- | --- |
| `node_id` | RouteDeck/navgraph node id. |
| `surface_id` | Active surface id. |
| `params` | Product-owned public location params. |
| `deeplink` | Copyable deeplink metadata. |

`RouteDeckNavigationState`

| Field | Meaning |
| --- | --- |
| `current` | Current `RouteDeckLocation`. |
| `back_stack` | Guarded RouteDeck location history. |
| `forward_stack` | Guarded forward history. |
| `can_back` | Whether back is legal. |
| `can_forward` | Whether forward is legal. |
| `can_cancel` | Whether cancel is legal. |

`RouteDeckNavGraph`

| Field | Meaning |
| --- | --- |
| `current` | Current RouteDeck location. |
| `nodes` | Runtime navgraph nodes. |
| `edges` | Runtime navgraph edges. |
| `traversed` | Node ids already traversed. |
| `reachable` | Node ids reachable from current state. |

`RouteDeckNavGraphNode`

| Field | Meaning |
| --- | --- |
| `id` | RouteDeck node id. |
| `label` | Product-facing node label. |
| `surface_id` | Surface associated with the node. |
| `deeplink` | Copyable address metadata. |
| `capability_ids` | Capabilities available at the node. |
| `metadata` | Sanitized node metadata. |

`RouteDeckNavGraphEdge`

| Field | Meaning |
| --- | --- |
| `from` | Source node id. |
| `to` | Target node id. |
| `action_id` | Operation associated with traversal. |
| `capability_id` | Capability associated with traversal. |
| `metadata` | Sanitized edge metadata. |

### Surface And Entity Schemas

`RouteDeckSurface`

| Field | Meaning |
| --- | --- |
| `name` | Slot or map key name. |
| `surface_id` | Stable surface id. |
| `component` | Product component contract name. |
| `variant` | Product component variant. |
| `role` | `frame`, `active`, or `diagnostic`. |
| `slot` | Product-defined slot. |
| `surface_kind` | `peer`, `detail`, or `embedded`. |
| `label` | Product-facing surface label. |
| `default` | Whether this is default for its role/location. |
| `props` | Sanitized props for rendering. |
| `lifecycle` | `ephemeral` or `stable`. |

`RouteDeckSurfaceAffordance`

| Field | Meaning |
| --- | --- |
| `surface_id` | Surface that emits the event. |
| `affordance_id` | Product event/affordance id. |
| `event` | Event name emitted by the surface. |
| `capability_id` | Capability represented by the affordance. |
| `operation_id` | Operation to dispatch after binding. |
| `entity_key` | Primary entity binding key. |
| `entity_keys` | Multiple entity binding keys. |
| `arg_bindings` | Binding expressions from entity or event payload. |
| `metadata` | Sanitized affordance metadata. |

`RouteDeckBindingExpression`

| Field | Meaning |
| --- | --- |
| `from` | `entity` or `event`. |
| `path` | Product-owned path inside the entity binding or event payload. |

`RouteDeckAvailableEntity`

| Field | Meaning |
| --- | --- |
| `kind` | Product entity kind. |
| `entity_key` | Stable public/context-local binding key. |
| `label` | Human and agent-readable label. |
| `parent_label` | Optional parent label. |
| `rendered_on` | Surface ids currently rendering the entity. |
| `operations` | Bound operation args available for this entity. |
| `metadata` | Sanitized entity metadata. |

`RouteDeckEntityOperationBinding`

| Field | Meaning |
| --- | --- |
| `operation_id` | Operation this entity can bind. |
| `args` | Runtime-dispatch args associated with this entity. |

### Event, Dispatch, And Diagnostics Schemas

`RouteDeckDispatchInput`

| Field | Meaning |
| --- | --- |
| `operation_id` | Product operation id. |
| `surface_event` | Surface event to resolve. |
| `args` | Operation args. |
| `graph_state` | Product-owned graph state snapshot or handle. |
| `projection_version` | Client projection version. |
| `context` | Product-owned request context metadata. |

`RouteDeckDispatchResult`

| Field | Meaning |
| --- | --- |
| `operation_id` | Operation id resolved by dispatch. |
| `accepted` | Whether runtime accepted the request. |
| `state` | Next `RouteDeckRuntimeState`. |
| `active_surface` | Active surface after dispatch. |
| `messages` | Product-facing result messages. |
| `events` | RouteDeck events caused by dispatch. |
| `metadata` | Product/framework metadata such as normalized path. |

`RouteDeckEvent`

| Field | Meaning |
| --- | --- |
| `event_type` | `projection_update`, `operation_started`, `operation_completed`, `graph_transition`, `guard_failure`, `surface_update`, or `runtime_status`. |
| `turn_id` | Product or runtime turn correlation id. |
| `projection_version` | Projection version associated with event. |
| `payload` | Event payload. |

`RouteDeckIntrospection`

| Field | Meaning |
| --- | --- |
| `current_node` | Current RouteDeck node. |
| `reachable_nodes` | Reachable node ids. |
| `legal_operations` | Legal operations for diagnostics. |
| `blocked_operations` | Blocked operations and reasons. |
| `guard_explanations` | Product-safe guard explanations. |
| `surfaces` | Surface diagnostics. |
| `route_traces` | Route trace diagnostics. |
| `diagnostics` | Additional sanitized diagnostics. |

`RouteDeckSemanticObservation`

| Field | Meaning |
| --- | --- |
| `type` | Product-owned observation type. |
| `summary` | Product-safe semantic summary. |
| `entity_key` | Related entity key. |
| `operation_id` | Related operation id. |
| `accepted` | Operation outcome when relevant. |
| `metadata` | Sanitized product-owned metadata. |

## Corpus Lessons Adopted Into RouteDeck

Corpus remains a product agent, not the framework. The reusable lessons RouteDeck
adopts are:

- product path segments own graph location
- `surface_id` query state owns active surface replay
- hidden `route.*` operations are infrastructure
- legal operations are not automatically quick actions
- product action chips belong to the assistant/workbench experience
- visible entities bind operation args for chat
- product surface intents are selected from `surface_options`
- browser replay is guarded location restoration
- diagnostics are read-only
- public chat has a stricter safety boundary than owner diagnostics
- React local state stores drafts, tabs, and display state only
- RouteDeckStore mirrors runtime state and never becomes graph truth

The product-specific Corpus details RouteDeck does not adopt are:

- SaaStoAgent prompts
- SaaS Agent domain behavior
- owner-workbench copy
- target API execution logic
- product account/auth semantics
- public deployed-chat wording
- SaaStoAgent database ids
- Corpus-specific route names outside the generic route-family pattern

## Medusa Barebones Proof Contract

The Medusa example currently needs a reset because the proof became a pile of
later-slice behavior. The required proof is smaller:

| Part | Contract |
| --- | --- |
| First screen | Chat, not landing page, workbench, diagnostics, navgraph, or product panel. |
| Required endpoint | `POST /api/medusa-agent/agent/stream`. |
| Optional endpoint | Health check only. |
| Stream | True SSE with `message_delta`. |
| Agent | Product-owned commerce assistant. |
| State | Process-local conversation state. |
| Model config | Product-owned. |
| Missing key behavior | SSE error, not fake assistant text. |
| RouteDeck | Completely absent. |
| Medusa Store API | Completely absent. |
| Cart/checkout/admin | Completely absent. |
| UI controls | Composer only, plus product-owned non-RouteDeck chat affordances if needed. |

What barebones Medusa is:

- a normal product app
- a normal product-owned chat stream
- an agent-first reference starting point
- a clean baseline for future RouteDeck adoption

What barebones Medusa is not:

- a RouteDeck demo
- a graph debugger
- a commerce workbench
- a Store API wrapper
- a navgraph showcase
- a deterministic command menu
- a fake all-slices demo

Future Medusa RouteDeck slices must reintroduce one layer at a time:

1. projection/state only, no operation execution
2. manifest/navgraph and read-only inspector
3. surface affordances with guarded dispatch
4. chat planning context and typed product-agent operation selection
5. commerce writes against a resettable local/demo fixture
6. diagnostics and packaging after product behavior is stable

## Acceptance Checklist

A RouteDeck-backed product passes the software-on-paper contract when all of the
following are true:

- product graph truth stays product-owned
- RouteDeck projection is output
- navgraph is graph topology, not a command menu
- navgraph node selection is read-only
- browser URL location uses product path segments
- query parameters hold optional presentation or surface state
- deeplinks never expose private ids
- product action chips are filtered and attached to assistant/workbench context
- hidden `route.*` operations stay hidden from ordinary product UI and planning
- every semantic surface action is represented in chat planning context
- chat dispatch and click dispatch converge on one runtime boundary
- product-agent SSE is separate from RouteDeck state SSE
- diagnostics stay read-only and out of public chat
- RouteDeckStore mirrors runtime state only
- product agents do not use deterministic phrase routers as the primary intent
  path
- product examples do not redefine framework semantics
- Medusa starts as barebones chat before RouteDeck is added again
