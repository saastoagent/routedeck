# Using RouteDeck For Agents, Humans, And Product Developers

Status: Practical usage guide
Date: 2026-05-26

RouteDeck is a graph-backed state runtime for agentic UI. It lets a product
graph expose what is currently true, what can be done next, which surfaces are
valid, which operations are safe to dispatch, and why something is blocked.

RouteDeck is not a chatbot, product shell, workflow database, auth layer, prompt
manager, SaaS integration runtime, or LLM router. It is the reusable state and
operation contract between a graph-owned application and agentic UI.

For the canonical framework reference, read
[`route-deck-reference.md`](./route-deck-reference.md).
For the narrative architecture article, read
[`route-deck-whitepaper.md`](./route-deck-whitepaper.md).
For the printable preview version, open
[`route-deck-whitepaper.html`](./route-deck-whitepaper.html).

## Short Version

```text
Product graph owns truth.
RouteDeck owns the generic runtime, projection, navigation, dispatch, and diagnostics contract.
Product adapters translate graph state into RouteDeck runtime state.
Product UI and product agents consume RouteDeck state and dispatch typed operations.
Product services execute domain work.
```

## Who Uses RouteDeck

RouteDeck has three user groups:

- human operators use product UI rendered from RouteDeck projections
- product agents use product-facing RouteDeck context to choose typed operations
- developers use RouteDeck contracts and diagnostics to keep graph behavior
  testable

Each group sees a different face of the same runtime state. Product UI should
use product language. Diagnostics may expose framework details.

## Core Concepts

### Manifest

The manifest is the static contract for a RouteDeck-backed product. It declares
the possible nodes, edges, operations, fields, policies, and surface metadata.

The manifest is not live state. It is the shape of what the graph may do.

### Runtime State

Runtime state is the current graph-backed state exposed through RouteDeck:

- graph state snapshot
- current node and surface
- legal operations
- blocked operations
- active surfaces
- navigation state
- diagnostics
- projection version
- runtime status

React may mirror runtime state through a RouteDeck store. React local state must
not become graph truth.

### Projection

Projection is the UI/agent-facing view of runtime state. It tells clients:

- where the user is
- what surfaces are valid
- which operation ids are legal
- which operations can dispatch now
- which operations need forms, selectors, confirmation, review, or recovery
- what diagnostics are available

Projection is output. It does not own graph behavior.

### Operations

Operations are typed actions that a user, component, or product agent can
dispatch.

Important metadata:

- `id`
- `label`
- `description`
- `category`
- `input_schema`
- `invocation_kind`
- `can_dispatch_now`
- `required_args`
- `missing_args`
- `accepted_arg_keys`
- `safety_class`
- `execution_mode`
- `target_node`

`legal_operations` does not mean "render all of these as buttons." A legal
operation may be direct, form-backed, selector-backed, surface-opening,
review-required, blocked, or hidden/internal.

### Surfaces

Surfaces are graph-declared UI regions. They tell the product shell what should
be visible without putting workflow truth in local React state.

Common roles:

- `frame` - stable surrounding context
- `active` - current working surface
- `diagnostic` - read-only inspection

Common kinds:

- `peer` - alternate same-node view
- `detail` - nested/review view
- `embedded` - supporting inline view

Product code renders React components for surfaces. RouteDeck projects which
surfaces are valid and active.

## Internal Navigation vs Product Planning

RouteDeck supports generic route operations:

- `route.open_node`
- `route.switch_surface`
- `route.back`
- `route.forward`
- `route.cancel`

These are useful for browser replay, history, runtime plumbing, and diagnostics.
In product integrations they should normally be `hidden` operations.

Do not expose them as default product vocabulary. A product agent should not
need to say "I will call `route.switch_surface`." It should choose a product
surface intent from valid surface options, and the product runtime can map that
intent to internal route dispatch after validation.

Decision table:

| Operation state | UI behavior | Agent behavior |
| --- | --- | --- |
| `can_dispatch_now=true`, `invocation_kind=direct` | one-click action allowed | dispatch if intent matches |
| `invocation_kind=form` | open form/review surface | collect fields, then dispatch |
| `invocation_kind=entity_selector` | open selector or bind selected entity | bind visible entity args or open selector |
| `invocation_kind=surface` | open product surface | choose surface when user asks for that workflow |
| `invocation_kind=hidden` | do not render as product action | use only through runtime/diagnostic controls |
| `execution_mode=review` | show proposal/review | do not execute side effect directly |
| `execution_mode=blocked` | show product-safe recovery | ask for allowed prerequisite |

## How Humans Should Experience RouteDeck

Humans should experience RouteDeck through product concepts:

- Workflows
- Current work
- Review
- Details
- Back
- Forward
- Cancel
- Policy candidate
- Execution trace

Avoid product-visible labels such as:

- RouteDeck node
- graph edge
- operation id
- trace id
- endpoint path
- internal slot name

Those can appear in diagnostics when the surface is explicitly diagnostic.

## How Product Agents Should Use RouteDeck

Product-agent loop:

```text
Read product-facing RouteDeck projection/planning context.
Interpret user intent against legal operations, visible entities, and surfaces.
Choose one typed product operation, choose a product surface intent, or clarify.
Dispatch through RouteDeck/runtime.
Read the returned state.
Respond from product policy and the new state.
```

Agent rules:

- Use only operations or surface options present in current product-facing context.
- Bind required product entities when the current surface exposes them.
- Dispatch directly only when readiness metadata allows it.
- Never mutate graph state directly from a prompt.
- Never infer hidden permissions from conversation alone.
- Never expose internal ids, endpoint paths, operation ids, trace ids, approval
  ids, or API auth details in public chat.

## How Developers Should Integrate RouteDeck

Backend runtime shape:

```python
class ProductRouteDeckRuntime:
    async def snapshot(self, context) -> RouteDeckRuntimeState: ...
    async def projection(self, context) -> RouteDeckProjection: ...
    async def dispatch(self, request, context) -> RouteDeckDispatchResult: ...
    async def inspect(self, query, context) -> RouteDeckIntrospection: ...
    async def stream(self, context) -> AsyncIterator[RouteDeckEvent]: ...
```

RouteDeck can be exposed as a distinct generic API plane:

```text
GET  /api/routedeck/manifest
GET  /api/routedeck/snapshot
GET  /api/routedeck/projection
POST /api/routedeck/dispatch
POST /api/routedeck/inspect
GET  /api/routedeck/stream
```

Product APIs can sit beside that RouteDeck API plane:

```text
GET  /api/<product>/state
GET  /api/<product>/stream
POST /api/<product>/action
GET  /api/diagnostics/stream
```

Use separate RouteDeck APIs when operators, agents, or debugger surfaces need a
clear framework boundary. The wrong boundary is not `/api/routedeck/*` itself;
the wrong boundary is putting product-specific semantics under that namespace,
for example `/api/routedeck/<product>/checkout` or a RouteDeck endpoint that
owns product auth, tenancy, payment, or business policy.

React integration:

```ts
const store = createRouteDeckStore({
  snapshotUrl: '/api/corpus/state',
  dispatchUrl: '/api/corpus/action',
  streamUrl: '/api/corpus/stream',
  inspectUrl: '/api/diagnostics/stream',
})
```

Mount once:

```tsx
<RouteDeckProvider store={store}>
  <ProductShell />
</RouteDeckProvider>
```

Use hooks:

- `useRouteDeckStore()`
- `useRouteDeckProjection()`
- `useRouteDeckSurface(name)`
- `useRouteDeckOperations()`
- `useRouteDeckOperation(id)`
- `useRouteDeckDispatch()`
- `useRouteDeckStatus()`
- `useRouteDeckDiagnostics()`
- `useRouteDeckInspect()`

## Boundary Rules

RouteDeck owns:

- product-neutral manifest schemas
- product-neutral runtime state schemas
- operation metadata and readiness
- projection helpers
- navigation state contract
- dispatch result contract
- React store and hooks
- generic diagnostics and debugger primitives
- validation helpers

Product graph owns:

- node catalog for the product
- operation handlers
- transition rules
- domain guard logic
- auth and tenancy semantics
- persistence
- product services
- side effects
- domain recovery

Product UI owns:

- visual design
- product copy
- form layouts
- record cards
- conversation wording
- public-safe response formatting
- mapping RouteDeck surfaces to React components
- deciding how legal operations appear to users

Product agent owns:

- interpreting natural language
- selecting typed operations
- asking product-safe clarifying questions
- resolving user-facing fields
- applying public/private safety policy

RouteDeck must not own:

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

## Surface And Node Modeling

Use same-node peer surfaces when the user remains in the same workflow:

- policy gaps vs failed executions
- list vs compact summary
- settings tabs
- filtered views

Use child/detail nodes when the user enters committed nested work:

- one policy candidate review
- one execution trace review
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

RouteDeck can expose diagnostics to owner/developer surfaces. Public chat needs
stricter formatting.

Public chat must not expose:

- operation ids
- endpoint paths
- trace ids
- approval ids
- cart ids
- internal slot names
- API auth details
- raw graph state
- raw JSON unless explicitly in a developer-only surface

Good blocked automation language:

```text
I found the item and size, but this store needs an owner-approved automation policy before I can manage carts for visitors.
```

Bad public language:

```text
Provide x-publishable-api-key or approval_id so I can call postCartLineItems.
```

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
- SaaS Agent services own deployed-agent domain behavior.
- Generated API tools and OpenAPI execution belong to SaaStoAgent services.
- Learning approval and instructions save are graph operations.

## Anti-Patterns

Avoid:

- rendering every `legal_operation` as a generic quick action
- showing `Open node` or `Switch surface` as ordinary product actions
- dispatching operations with missing required args
- letting React local state own graph truth
- putting product ids or services into RouteDeck framework source
- calling product REST mutations directly when a graph operation exists
- exposing RouteDeck terms in public product UI
- treating public chat as diagnostics
- putting product-specific behavior inside `/api/routedeck/*`
- drawing action ids as navgraph edges
- adding backend phrase tables or alias routers for normal chat

## Checklist For New Integrations

- Manifest/projection validates.
- Every operation has scoped availability.
- Operation readiness is projected.
- Direct dispatch requires `can_dispatch_now=true`.
- Forms, selectors, surfaces, and hidden operations render differently.
- Product side effects go through graph operations.
- Product UI uses product language.
- Diagnostics are separate from public UI.
- Public chat output is safe.
- Raw framework routes are not exposed publicly.
- RouteDeck framework source has no product literals.
- Boundary tests cover planning context and UI filtering.
