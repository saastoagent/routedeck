# Using RouteDeck For Agents And Humans

Status: Practical usage guide
Date: 2026-05-25

RouteDeck is a graph-backed state runtime for agentic UI. It lets a product graph expose what is currently true, what can be done next, which surfaces should be visible, and which operations are safe to dispatch.

This guide explains how humans, product agents, and developers should use RouteDeck without collapsing product logic into the framework.

## Short Version

```text
Product graph owns truth.
RouteDeck owns the generic runtime, projection, navigation, dispatch, and diagnostics contract.
Product adapters translate graph state into RouteDeck state.
Product UI and product agents consume RouteDeck state and dispatch typed operations.
Product services execute domain work.
```

RouteDeck is not a chatbot, product shell, workflow database, auth layer, prompt manager, or SaaS integration runtime. It is the state and operation contract between a graph-owned application and agentic UI.

## Who Uses RouteDeck

RouteDeck has three user groups:

- Human operators use RouteDeck-projected UI to understand where they are, what workflow is active, what operations are available, and what needs review.
- Product agents use RouteDeck projections to choose typed legal operations instead of inventing state changes or calling product APIs directly.
- Developers use RouteDeck contracts, adapters, and diagnostics to keep graph navigation, surfaces, operation readiness, and product boundaries testable.

Each group sees a different face of the same runtime state.

## Core Concepts

### Manifest

The manifest is the static contract for a RouteDeck-backed application. It declares:

- nodes
- edges
- actions
- fields
- policies
- test paths
- hierarchy metadata
- surface availability

The manifest is not the live state. It is the shape of what the graph may do.

### Runtime State

Runtime state is the current graph-backed state exposed through RouteDeck. It includes:

- current node
- current surface
- graph state snapshot
- legal operations
- blocked operations
- navigation state
- diagnostics
- runtime status
- projection version

Runtime state is rebuilt from the product graph or product runtime adapter. React state may mirror it, but React state must not become the source of truth.

### Projection

The projection is the UI-facing view of runtime state. It tells the UI and agent:

- where the user is
- what surfaces are available
- which operation ids are legal
- which operations are directly dispatchable
- which operations require forms, entity binding, or review
- what diagnostics are available

Projection is an output, not the owner of graph behavior.

### Operations

Operations are typed actions that an agent or UI can dispatch.

Every operation should include enough metadata for generic clients to behave safely:

- `id`
- `label`
- `description`
- `category`
- `input_schema`
- `invocation_kind`
- `can_dispatch_now`
- `required_args`
- `missing_args`
- `safety_class`
- `execution_mode`
- `target_node`

`legal_operations` does not mean "render this as a one-click button." A legal operation may still need a form, selector, confirmation, owner approval, or product-specific surface.

### Surfaces

Surfaces are graph-declared UI regions. They are how the graph tells the product shell what should be visible.

Common roles:

- `frame`: stable context around the active work
- `active`: the current working surface
- `diagnostic`: read-only developer or owner inspection

Common kinds:

- `peer`: same-node alternate view
- `detail`: record-specific or nested view
- `embedded`: supporting inline surface

Product code renders the actual React components, but RouteDeck projects which surfaces are valid and active.

### Navigation

RouteDeck v2 treats navigation as a first-class runtime concept:

- `route.open_node`
- `route.switch_surface`
- `route.back`
- `route.forward`
- `route.cancel`

For the current implementation pass, back and forward history can be client-store-owned. Graph-committing operations still need backend validation.

Same-node peer surface switches should not create a workflow transition. Detail views should be child nodes when they represent committed nested work.

## How Humans Should Use RouteDeck UI

Humans should experience RouteDeck through product language, not framework internals.

Good product labels:

- Workflows
- Current workflow
- Review
- Details
- Back
- Forward
- Cancel
- Policy candidate
- Execution trace

Avoid product-visible labels such as:

- RouteDeck node
- operation id
- graph edge
- trace id in public chat
- internal slot name
- endpoint path

Developer and owner diagnostics may expose technical labels when the surface is clearly diagnostic.

## How Product Agents Should Use RouteDeck

A product agent should treat RouteDeck as the source for what can happen next. The agent should not infer hidden graph permissions from conversation alone.

Agent loop:

```text
Read RouteDeck projection.
Interpret user intent against legal operations and current surfaces.
Choose one typed operation or ask a product-safe clarification.
Bind required product entities if available.
Dispatch through RouteDeck.
Read the returned runtime state.
Respond from the new state and product policy.
```

Agent rules:

- Use only operation ids present in the current projection.
- Dispatch directly only when `can_dispatch_now=true`.
- Use `invocation_kind=form` to open or fill a form.
- Use `invocation_kind=entity_selector` to bind an entity before dispatch.
- Use `invocation_kind=surface` to open a product surface.
- Never mutate graph state directly from a prompt.
- Never call product side-effect APIs from public chat when a graph operation exists.
- Never expose internal ids, endpoint paths, operation ids, or trace ids in public chat.

## How Developers Should Integrate RouteDeck

### Backend Integration

Create a product adapter that implements the RouteDeck runtime contract:

```python
class ProductRouteDeckRuntime:
    async def snapshot(self, context) -> RouteDeckRuntimeState: ...
    async def projection(self, context) -> RouteDeckProjection: ...
    async def dispatch(self, request, context) -> RouteDeckDispatchResult: ...
    async def inspect(self, query, context) -> RouteDeckIntrospection: ...
    async def stream(self, context) -> AsyncIterator[RouteDeckEvent]: ...
```

The adapter may call product graph/runtime methods. It should not contain domain business behavior itself.

Recommended backend route shape:

```text
GET  /api/<product>/state
GET  /api/<product>/stream
POST /api/<product>/action
GET  /api/diagnostics/stream
```

Avoid raw public framework routes such as `/api/routedeck/*` in product apps unless they are explicitly internal diagnostics.

### React Integration

Create a RouteDeck store from product endpoints:

```ts
const store = createRouteDeckStore({
  initialState,
  snapshotUrl: '/api/corpus/state',
  dispatchUrl: '/api/corpus/action',
  streamUrl: '/api/corpus/stream',
  inspectUrl: '/api/diagnostics/stream',
})
```

Mount it once:

```tsx
<RouteDeckProvider store={store}>
  <ProductShell />
</RouteDeckProvider>
```

Use hooks:

```ts
const projection = useRouteDeckProjection()
const state = useRouteDeckState()
const dispatch = useRouteDeckDispatch()
const store = useRouteDeckStore()
```

Product UI should render product components from projected surfaces. It should not hardcode workflow truth in local state.

## Boundary Rules

### RouteDeck Owns

- product-neutral manifest schemas
- product-neutral runtime state schemas
- product-neutral operation metadata
- projection helpers
- navigation state contract
- dispatch result contract
- React store and hooks
- generic diagnostics and debugger primitives
- validation helpers
- optional product-neutral adapters

### Product Graph Owns

- node catalog for the product
- operation handlers
- transition rules
- domain guard logic
- auth and tenancy semantics
- persistence
- product services
- side effects
- domain recovery

### Product UI Owns

- visual design
- product copy
- form layouts
- record cards
- conversation wording
- safe public response formatting
- mapping RouteDeck surfaces to React components
- deciding how legal operations appear to users

### Product Agent Owns

- interpreting natural language against the projection
- selecting typed operations
- asking product-safe clarifying questions
- resolving user-facing fields
- delegating internal dependencies to graph-approved operations
- applying domain-specific public safety policy

### RouteDeck Must Not Own

- product prompts
- product auth
- product database models
- product route literals
- product node ids in reusable source
- SaaS provider behavior
- OpenAPI execution logic
- LLM provider calls
- payment or checkout behavior
- public chat copy

## Operation Readiness Rules

Use this decision table:

| Operation state | UI behavior | Agent behavior |
| --- | --- | --- |
| `can_dispatch_now=true`, `invocation_kind=direct` | one-click action allowed | dispatch if intent matches |
| `invocation_kind=form` | open form or proposal | collect fields, then dispatch |
| `invocation_kind=entity_selector` | open selector or bind selected entity | bind entity id from visible context, otherwise open selector |
| `invocation_kind=surface` | switch or open surface | open surface when user asks for that workflow |
| `invocation_kind=hidden` | do not render as product action | use only through explicit runtime controls |
| `execution_mode=review` | show review/proposal | do not execute side effect directly |
| `execution_mode=blocked` | show recovery if product-safe | ask for allowed prerequisite or owner action |

## Surface And Node Modeling

Use same-node peer surfaces when the user is still in the same workflow:

- policy gaps vs failed executions
- list vs compact summary
- settings tabs
- filtered views

Use child/detail nodes when the user enters committed nested work:

- one policy candidate review
- one execution trace review
- one active policy review
- one selected record editor

Use a new top-level node when the user changes capability:

- Home
- Agent setup
- Connect API
- Catalog
- Execution
- Knowledge
- Learning
- QA

## Public Chat Safety

RouteDeck can expose diagnostics to owner surfaces. Public chat needs stricter formatting.

Public chat must not expose:

- operation ids
- endpoint paths
- trace ids
- cart ids
- internal slot names
- API auth details
- raw graph state
- raw JSON unless explicitly in a developer-only surface

Public chat should phrase blocked internal automation as product policy:

```text
I found the item and size, but this store needs an owner-approved automation policy before I can manage carts for visitors.
```

Owner diagnostics may show the policy candidate, allowed action chain, trace, missing dependency, and generated action paths.

## SaaStoAgent Boundary Example

SaaStoAgent currently uses this layering:

```text
SaaStoAgent product graph
  -> CorpusRouteDeckRuntime
    -> RouteDeckRuntimeState
      -> /api/corpus/state, /api/corpus/action, /api/corpus/stream
        -> @routedeck/react store
          -> Corpus product shell and diagnostics
```

In this model:

- RouteDeck owns generic projection and dispatch mechanics.
- Corpus owns the SaaStoAgent builder experience.
- SaaSAgent owns deployed-agent domain behavior.
- Generated API tools and OpenAPI execution belong to SaaStoAgent services, not RouteDeck.
- Learning approval and instructions save are graph operations, not direct surface mutations.

## Diagnostics

Diagnostics are for developers and owners, not public users.

Good diagnostics show:

- current node
- current surface
- legal operations
- blocked operations
- guard explanations
- route trace
- runtime snapshot
- selected-node operation metadata
- hierarchy and containment

Diagnostics should avoid making action ids look like graph topology. Navigation and containment edges belong on the graph. Actions belong in selected-node details or operation diagnostics.

## Anti-Patterns

Avoid these:

- Rendering every `legal_operation` as a generic quick action.
- Dispatching an operation with missing required args.
- Letting a React store own graph truth.
- Putting product ids or product services into RouteDeck framework source.
- Calling product REST mutation APIs directly from a RouteDeck-backed surface when a graph operation exists.
- Exposing RouteDeck terms in public product UI.
- Treating public chat as a diagnostics surface.
- Making `/api/routedeck/*` public product routes.
- Drawing action ids as navgraph edges.
- Adding compatibility bridges for removed navigation contracts unless explicitly required.

## Checklist For New RouteDeck Integrations

Before shipping a RouteDeck-backed product flow:

- Manifest validates.
- Every graph node has a handler.
- Every operation has scoped allowed nodes.
- Operation readiness is projected.
- Direct dispatch requires `can_dispatch_now=true`.
- Forms, selectors, surfaces, and hidden operations render differently.
- Product side effects go through graph operations.
- Product UI uses product language.
- Diagnostics are separate from public UI.
- Public chat output is safe.
- Raw framework routes are not exposed unless diagnostic-only.
- RouteDeck framework source has no product literals.
- Boundary tests cover the product integration.

## When To Add RouteDeck Features

Add a feature to RouteDeck when it is product-neutral and reusable across apps:

- better runtime state contract
- better operation readiness model
- better navigation state
- better diagnostics
- better graph validation
- better React store or hooks
- product-neutral adapter support

Keep it in the product when it depends on:

- product entities
- product copy
- product auth
- product persistence
- domain policy
- target API behavior
- payment, checkout, catalog, customer, or account semantics

## Related Docs

- `docs/agentic-ui-state-runtime.md`
- `docs/boundary.md`
- `docs/framework-architecture.md`
- `agent-lab-powered-projects/saastoagent-v0.1/decisions/ADR-013-routedeck-corpus-boundary.md`
