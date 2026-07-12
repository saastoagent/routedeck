# Using RouteDeck For Agents, Humans, And Product Developers

Status: Practical usage guide
Date: 2026-07-10

RouteDeck is a full-stack framework for robust agentic applications, with an
embeddable state and interaction runtime for existing agents. It lets a product
declare what is true, what can be done next, which surfaces are valid, which
operations are safe to dispatch, and why something is blocked.

RouteDeck does not own product prompts, product auth, product databases, domain
side effects, or product copy. It owns the reusable application compiler/runtime,
state and interaction kernel, typed event/SSE architecture, projection, and
frontend state path around those product concerns.

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

RouteDeck has two developer adoption modes and three runtime audiences:

- Full Flow developers declare an app and let RouteDeck compile and run the
  LangGraph-backed backend, event, SSE, projection, and React state path.
- Core Integration developers keep an existing agent or custom graph and attach
  it to the same RouteDeck kernel through an executor adapter.

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
Surfaces present product/runtime capabilities. They do not own capabilities and
they do not bypass dispatch.

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

Surface affordances declare what a rendered component can emit:

```json
{
  "surface_id": "detail.product_detail",
  "affordance_id": "add_to_cart",
  "operation_id": "cart.add_item",
  "entity_key": "variant:s-black"
}
```

The same capability must be available to chat through planning context. A user
clicking `Add to cart` and a user saying "add the small black shirt" resolve to
the same operation and entity key before dispatch.

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
| `invocation_kind=entity_selector` | open selector or bind selected entity | bind available/selectable entity args or open selector |
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
Interpret user intent against legal operations, available entities, surface affordances, and surfaces.
Choose one typed product operation, choose a product surface intent, or clarify.
Dispatch through RouteDeck/runtime.
Read the returned state.
Respond from product policy and the new state.
```

Agent rules:

- Use only operations or surface options present in current product-facing context.
- Bind required product entities from available/selectable entities in planning context.
- Treat rendered entities as a UI subset of available entities, not the full chat context.
- Dispatch directly only when readiness metadata allows it.
- Never mutate graph state directly from a prompt.
- Never infer hidden permissions from conversation alone.
- Never expose internal ids, endpoint paths, operation ids, trace ids, approval
  ids, or API auth details in public chat.

## How Developers Should Integrate RouteDeck

### Full Flow

Use Full Flow when RouteDeck should own the public interaction graph and
supervision kernel. Features declare nodes and local transitions; the
application composes cross-feature transitions once:

```python
from routedeck_core.app import (
    ApplicationSpec,
    FeatureBindings,
    bind_app,
    compile_app,
)

spec = ApplicationSpec(
    name="support-agent",
    entry_node=SUPPORT_HOME.ref,
    features=(SUPPORT_FEATURE, ACCOUNT_FEATURE),
    transitions=SUPPORT_CROSS_FEATURE_TRANSITIONS,
)

compiled = compile_app(spec)
app = bind_app(
    compiled,
    FeatureBindings(
        handlers=SUPPORT_HANDLERS,
        providers=SUPPORT_PROVIDERS,
        guards=SUPPORT_GUARDS,
    ),
)
```

`compile_app` validates the complete declaration. `bind_app` then requires the
exact async handler, provider, and guard references: missing and extra bindings
are startup errors. The composition root injects the session store, executor,
clock, notifier, and ID factory into `RouteDeckOperationRunner`, then mounts the
generic FastAPI router. See the Medusa app's `composition.py` and `runtime.py`
for the working end-to-end composition.

### Core Integration

Use Core Integration when execution already exists. Keep the product graph,
model, and tool topology; inject an `OperationExecutor` implementation into the
same `RouteDeckOperationRunner`:

```python
runner = RouteDeckOperationRunner(
    app=bound_app,
    store=session_store,
    executor=existing_operation_executor,
    clock=clock,
    notifier=notifier,
    id_factory=id_factory,
    review_ttl=review_ttl,
    resume_capability_ttl=resume_ttl,
    default_session_id=default_session_id,
)
```

The executor receives only an already validated `OperationBinding`, typed
arguments, and `ExecutionContext`. It does not redefine RouteDeck operations,
guards, events, surfaces, projections, or store semantics. A LangGraph product
normally keeps its own `create_agent(...)` graph and uses
`RouteDeckMiddleware` plus `RouteDeckToolWrapper` to enter this runner.

### Runtime Contract

Both modes use the same backend ports and supervised request shape:

```python
result = await runner.run(
    OperationRequest(
        session_id=session_id,
        request_id=request_id,
        expected_session_version=session_version,
        operation_id="support.open_ticket",
        source=OperationSource.SURFACE,
        arguments={"ticket_handle": ticket_handle},
    )
)
```

The reference FastAPI adapter exposes a distinct generic API plane:

```text
GET  /api/routedeck/contract
POST /api/routedeck/sessions
GET  /api/routedeck/session
POST /api/routedeck/navigation
POST /api/routedeck/dispatch
POST /api/routedeck/reviews/{review_id}/accept
POST /api/routedeck/reviews/{review_id}/reject
GET  /api/routedeck/events
GET  /api/routedeck/private-forms/{form_id}
PUT  /api/routedeck/private-forms/{form_id}
GET  /api/routedeck/inspect
```

Product auth dependencies remain injected. RouteDeck owns route mechanics and
schemas; product-specific checkout, tenancy, billing, or provider semantics
remain in product handlers. Product-owned endpoints such as agent chat live on
a separate product API plane.

`POST /api/routedeck/sessions` takes `{"request_id":"..."}`. Dispatch,
navigation, reviews, private-form saves, and product chat likewise carry a
caller-owned globally unique request ID; versioned mutations also carry the
current expected session version. If delivery becomes outcome-unknown, retain
the exact ID and payload and require an explicit retry or abandon decision.
Never auto-retry a state-changing request with a new identity.

A session-create request ID is sensitive, ephemeral recovery material: exact
replay can recover the original guest session and browser cookie. Keep it only
inside private recovery storage. Never expose it, or a reversible fingerprint
that contains it, through public store state, rendered UI, logs, or telemetry;
public recovery surfaces should report generic status or a non-replayable
fingerprint.

React integration:

```ts
const store = createRouteDeckStore({
  contractUrl: '/api/support/contract',
  sessionUrl: '/api/support/sessions/session-1',
  channels: ['assistant', 'runtime', 'surface'],
})
```

The store loads the versioned client contract derived from the backend
application specification. Product frontend code registers React components by
declared component key; it does not repeat nodes, flows, operations, or surface
policy.

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
- making navgraph nodes clickable dispatch or navigation controls
- changing the browser URL from a navgraph click instead of from projected
  navigation/deeplink state
- making query-only `?rd_node=...` URLs the canonical public browser deeplinks
  for a new product instead of a product-owned path codec like the Corpus
  integration
- rendering product action chips in the navgraph or inspector instead of the
  product chat/assistant experience
- merging product surfaces with navgraph/inspector UI so product clicks appear
  to be graph navigation
- showing same-node legal operations as ordinary next-action chips unless the
  product deliberately labels them as refresh/reload controls
- hiding action, entity, or affordance detail inside the graph canvas instead of
  a read-only inspector or diagnostics surface
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
