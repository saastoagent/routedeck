# Using RouteDeck

Status: current developer guide
Date: 2026-07-17

RouteDeck lets product developers focus on features. A feature declares complete
interaction nodes and supplies product behavior; RouteDeck composes, validates,
and runs the shared state, supervision, navigation, conversation, and browser
machinery.

## Mental Model

```text
feature declarations + product implementations
  -> compile and bind
  -> one RouteDeck runtime
  -> optional FastAPI and LangGraph adapters
  -> @routedeck/core authoritative browser state
  -> @routedeck/react product-neutral UI primitives
```

The navgraph is the durable product interaction map. It does not replace a
product-owned LangGraph graph.

## 1. Author A Complete Feature

A feature owns complete nodes. Each node declares what is meaningful at that
location:

- route and optional route-entry operation;
- context/entity providers and guards;
- operations and declared outcomes;
- surfaces, capabilities, and suggested actions;
- static conversation-input availability and consumer-owned disabled copy;
- outgoing transitions;
- navigation and recovery policy.

```python
from routedeck_core.app import Feature
from routedeck_core.contracts.application import Node, RouteEntry
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    NodeRef,
    Route,
    Transition,
)

PRODUCT = Node(
    id="catalog.product",
    title="Product",
    kind=NodeKind.DETAIL,
    route=Route(
        template="/products/{product_handle}",
        deep_link_policy=DeepLinkPolicy.SHAREABLE,
    ),
    entry=RouteEntry(
        operation=OPEN_PRODUCT_BY_ROUTE.ref,
        outcome="opened",
        bindings=(PRODUCT_HANDLE_BINDING,),
    ),
    operations=(OPEN_PRODUCT_BY_ROUTE, ADD_ITEM),
    outgoing=(
        Transition(
            operation=ADD_ITEM.ref,
            outcome="added",
            target=NodeRef(id="cart.summary"),
        ),
    ),
    surfaces=PRODUCT_SURFACES,
)

FEATURE = Feature(namespace="catalog", nodes=(PRODUCT,))
```

Transition source is implicit from the declaring node. RouteDeck derives
incoming adjacency after all selected features are known. Do not maintain a
second global edge table.

Cross-feature targets are allowed. They fail compilation if the target feature
is not selected, which keeps missing dependencies explicit.

## 2. Keep Composition Small

The application composition root selects features and one entry node:

```python
from routedeck_core.app import Application

APP = Application(
    name="buyer",
    entry_node=BUYER_HOME.ref,
    features=(CATALOG_FEATURE, CART_FEATURE, CHECKOUT_FEATURE, ORDER_FEATURE),
)
```

`compile_app(APP)` resolves and validates the complete graph, routes, operation
catalogs, surfaces, frontend contract, and executable paths. It fails loudly on
duplicate ownership, unknown references, route ambiguity, missing outcomes,
invalid schemas, incomplete recovery, or unreachable nodes.

Composition should not assemble transitions, copy feature nodes, patch models,
or infer dependencies.

## 3. Bind Product Behavior

Declarations describe the contract. Bindings supply real implementations:

```python
bindings = FeatureBindings.merge(
    create_catalog_bindings(store_client),
    create_cart_bindings(store_client),
    create_checkout_bindings(store_client, private_forms),
)
bound = bind_app(compiled, bindings)
```

Every declared operation, provider, and guard must have exactly one correctly
shaped async implementation. Extra or missing bindings are startup errors.

Product handlers own domain correctness and side effects. RouteDeck owns the
supervision around the call. Handlers return typed outcomes/effects/failures;
they do not patch RouteDeck state directly.

## 4. Model Routes And Handles Deliberately

Use `shareable` for routes that may open without an existing session. Use
`session_bound` when the path exposes private or session-specific state.

A dynamic shareable route uses a declared `RouteEntry` to bind exact path
parameters to a supervised product operation. RouteDeck parses the path;
product code resolves the public route key from its source of truth.

Real IDs remain product-private. Providers add classified bindings and expose
opaque handles. Agent/browser arguments resolve only when the current session,
node, operation, entity kind, and allowlist agree.

## 5. Declare Surfaces, Not Product UI In The Framework

`Surface` declares component identity, lifecycle, public props schema, and
operation-backed affordances. Product React code registers the component name
and renders the visual design.

- Stable public surface state survives navigation for exact history restore.
- Ephemeral state survives only while the current node declares the surface.
- Private forms use a server-only `PrivateFormBinding`; private values never
  enter projection, events, inspection, frontend contracts, or model context.

A surface affordance and an agent tool dispatch the same declared operation.
The Navgraph inspector is orientation-only and never dispatches or navigates.

The React surface registry must match the unique component names in the
compiled frontend contract exactly. `RouteDeckSurfaceHost` fails visibly for
missing registrations and stale extras instead of discovering drift only when
a particular surface becomes active.

Projected surfaces remain mounted but busy and inert while the canonical
client store is bootstrapping, navigating, reconnecting, or resynchronizing.
Do not add product-owned readiness checks or call operation dispatch around the
Surface host; controls become interactive only after the store returns to
`live`.

## 6. Open One Runtime

For durable applications, pass product inputs to the SQLAlchemy opener:

```python
application = await open_sqlalchemy_routedeck_runtime(
    compiled_app=compiled,
    application_factory=bind_product_application,
    session_factory=create_product_session,
    session_initializer=initialize_product_session,
    public_key_validator_factory=create_route_key_validator,
    agent_driver_factory=optional_graph_driver_factory,
    database_url=settings.database_url,
    encryption_key=settings.encryption_key,
    instance_id=settings.instance_id,
)
```

The framework opens persistence and constructs one operation runner,
navigation over that runner, projection, optional agent driver, and explicit
lifecycle. Product code does not construct those generic objects.

Use an explicit SQLite or PostgreSQL URL. A database, encryption, lease, graph,
or callback failure propagates; no alternate resource is selected.

## 7. Mount The Generic HTTP Plane

The product host mounts one router derived from its runtime:

```python
from routedeck_fastapi import (
    GuestCookieSessionSelector,
    GuestCookieSettings,
    create_routedeck_router_from_runtime_provider,
)

session_selector = GuestCookieSessionSelector(
    GuestCookieSettings(
        name="routedeck_guest",
        secure=True,
        path="/",
    )
)

app.include_router(
    create_routedeck_router_from_runtime_provider(
        runtime_provider,
        session_selector=session_selector,
    )
)
```

The generic plane provides contract, session, navigation, operation/review,
conversation, event, private-form, and inspection routes. Product health,
authentication, CORS/origin configuration, and domain routes remain product
owned.

RouteDeck ships the explicit guest-cookie selector shown above for guest mode.
Use `secure=True` on HTTPS; the Medusa local HTTP demo deliberately configures
`False`. Authenticated users and multiple sessions require a consumer-owned
`RouteDeckSessionSelector` that authorizes an opaque product session handle
against the current principal before returning an internal RouteDeck session
ID. RouteDeck does not own users or trust raw internal IDs from a browser.

## 8. Integrate A Product-Owned Agent

Keep the product's `create_agent(...)` or raw `StateGraph`. RouteDeck supplies:

- `RouteDeckMiddleware` for durable conversation and default-deny context;
- `RouteDeckToolWrapper` for runner-owned schema tools;
- `RouteDeckLangGraphDriverFactory` for generic stream translation;
- explicit user-message and assistant-initiated triggers.

The product supplies graph topology, prompts, model roles, policy, wording, and
an explicit graph set. Returning `None` makes conversation unavailable; it does
not select a fallback model.

Every product tool call crosses the same operation runner as a UI affordance.
See `skills/routedeck-langgraph-integration/SKILL.md` for the focused wiring
recipe.

## 9. Bootstrap The Browser

`@routedeck/core` loads the compiled frontend contract and creates the store.
Provide the route codec and history adapter when routes are enabled.

For `resume_or_create_shareable` bootstrap:

1. capture the incoming browser path;
2. try the current guest session;
3. on missing/expired/contract-mismatch, create one session only if the captured
   route is shareable;
4. reconcile the captured route through server navigation;
5. write only the confirmed projection to browser history;
6. start event synchronization.

Session-bound links do not create replacement state. Outcome-unknown creation
or navigation retains the exact request ID and payload for explicit recovery.

Use the React boundary without decoding `pendingBootstrap`,
`pendingNavigation`, or retry legality in product code:

```tsx
import { RouteDeckBootstrapBoundary } from "@routedeck/react";

<RouteDeckBootstrapBoundary
  store={store}
  loading={<ProductLoading />}
  recovery={(state) => <ProductRecovery state={state} />}
>
  <App />
</RouteDeckBootstrapBoundary>;
```

The recovery renderer owns product copy, styling, and policy. It must invoke
only actions present in `state.actions`; RouteDeck maps uncertain creation,
expired/missing/contract-mismatched resume, uncertain navigation, resync, and
disposal to the legal action set. For custom composition use
`useRouteDeckBootstrapRecovery(store)` directly.

`@routedeck/react` also supplies provider/hooks, conversation presentation,
surface host, operations, private forms, review, navigation, status/error, and
read-only Navgraph primitives. Product components and copy remain outside the
framework package.

Use `useRouteDeckConversationInputPolicy()` to drive a product composer from
the current node's compiled policy. Do not maintain a second frontend list of
node IDs. RouteDeck validates and resolves the policy; the product declares
which nodes disable input and supplies the displayed reason.

## 10. Preserve Failure Semantics

- Caller-owned request IDs are immutable replay identities.
- Reusing an ID with different input is a contract error.
- A received `4xx` is a confirmed rejection.
- Lost/malformed success responses and relevant `5xx` results are
  outcome-unknown because the server may have committed.
- External writes are never silently retried after uncertain delivery.
- Missing data, credentials, models, guards, bindings, or invariants fail
  visibly.
- Fixtures and scripted models stay in explicitly test-only packages/paths.

## Integration Checklist

- [ ] Features own complete nodes and outgoing transitions.
- [ ] Composition only selects features and the entry node.
- [ ] Every declaration has one feature-owned binding.
- [ ] Product IDs remain behind current opaque-handle allowlists.
- [ ] UI and agent operations share one runner.
- [ ] Product graph topology remains product-owned.
- [ ] Runtime and FastAPI dependencies come from RouteDeck builders.
- [ ] Browser state confirms only server projection and exact history.
- [ ] Session authorization remains consumer-owned.
- [ ] Missing dependencies fail without substitutes.
- [ ] Focused proof is selected from `test_index/README.md`.

For the complete contract see `docs/route-deck-reference.md`. For
feature-to-code-to-test ownership see `architecture/feature-coverage.md`.
