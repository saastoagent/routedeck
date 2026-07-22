# Applications and the Navgraph

RouteDeck authoring is feature-first. Each feature owns complete nodes; the
composition root only selects features and one entry node.

## Node-owned structure

A node may declare:

- stable ID, title, kind, parent, and route;
- optional route-entry operation;
- context and entity providers;
- guards and legal operations;
- capabilities and surfaces;
- node-owned outgoing transitions;
- navigation, recovery, suggestions, and public metadata.

The source of a transition is implicit from the declaring node:

```python
PRODUCT = Node(
    id="catalog.product",
    title="Product",
    kind=NodeKind.DETAIL,
    route=Route(
        template="/products/{product_handle}",
        deep_link_policy=DeepLinkPolicy.SHAREABLE,
    ),
    operations=(ADD_ITEM,),
    outgoing=(
        Transition(
            operation=ADD_ITEM.ref,
            outcome="added",
            target=NodeRef(id="cart.summary"),
        ),
    ),
    surfaces=PRODUCT_SURFACES,
)
```

Cross-feature transitions are allowed. Compilation fails if their selected
target feature is absent.

## Composition

```python
APP = Application(
    name="buyer",
    entry_node=BUYER_HOME.ref,
    features=(CATALOG_FEATURE, CART_FEATURE, CHECKOUT_FEATURE, ORDER_FEATURE),
)
```

Composition does not copy nodes, patch models, recreate transitions, or infer
feature dependencies.

## Compilation

`compile_app(...)` creates one `CompiledApplication` with:

- immutable node lookup and `require_node(...)`;
- flattened operations, providers, guards, capabilities, and surfaces;
- compiled normalized routes;
- complete transition and incoming adjacency;
- versionable frontend contract;
- derived executable test paths.

It rejects duplicate IDs, route overlap, unknown references, invalid route
bindings, undeclared outcomes, ambiguous branches, unreachable nodes, invalid
public schemas, or incomplete write-recovery declarations.

## Route entry

An incoming dynamic path becomes authoritative through an exact declared
operation:

```python
entry=RouteEntry(
    operation=OPEN_PRODUCT_BY_ROUTE.ref,
    outcome="opened",
    bindings=(
        RouteParameterBinding(
            parameter="product_handle",
            argument="product_handle",
        ),
    ),
)
```

RouteDeck parses structure and supervises the operation. Product code resolves
the public key against the product's real source of truth. Regex guessing,
phrase routing, or scanning private entities is not a substitute.

## Exact bindings

Declarations say what may happen. `FeatureBindings` supplies what actually
happens. `bind_app(...)` requires exactly one correctly shaped async handler,
provider, and guard for each declaration, with no extras.

```python
bindings = FeatureBindings.merge(
    create_catalog_bindings(store_client),
    create_cart_bindings(store_client),
)
bound = bind_app(compiled, bindings)
```

Binding failures are startup errors. They do not select placeholder behavior.

## Navgraph versus sitemap

A sitemap describes pages. A RouteDeck navgraph additionally describes the
legal semantic operation and exact outcome that reaches each target. The
read-only Navgraph inspector visualizes this compiled contract, but selecting
a diagnostic node does not navigate or mutate the application.

Next: [Operations and Supervision](./Operations-and-Supervision.md).
