# RouteDeck Feature-Owned Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make RouteDeck own graph composition so product developers author feature nodes and node-owned outgoing transitions while consumer applications only select features and an entry node.

**Architecture:** The authoring layer exposes plain domain names and stores source-implicit `Transition` values on `Node.outgoing`. `compile_app()` materializes explicit `CompiledTransition` values, derives an immutable incoming index, validates the complete selected-feature graph, and returns `CompiledApplication`. Medusa moves all current composition-time node augmentation into feature declarations; its composition root becomes an immutable application manifest plus compile function.

**Tech Stack:** Python 3.11+, Pydantic 2, pytest 9, RouteDeck core/adapters, Medusa reference application, Playwright for the final local checkout proof.

## Global Constraints

- This is a clean break: do not add aliases for old `*Spec`, `CompiledRouteDeckApp`, `BoundRouteDeckApp`, `FEATURE_SPEC`, `MEDUSA_APP_SPEC`, or `compile_medusa_app_spec` names.
- RouteDeck owns composition, reference resolution, incoming-edge derivation, validation, and compilation.
- Feature authors own nodes and each node's outgoing transitions.
- `Application` contains only `name`, `entry_node`, and `features`; `Feature` contains its namespace, nodes, and agent policies, but no transitions registry.
- Runtime handlers, providers, bindings, persistence, transport, and LangGraph construction remain outside application composition.
- Cross-feature declaration modules expose stable identities and reusable declarations only; they are not facets, contributions, overlays, registries, or extension points.
- Missing references and invalid branches fail loudly with feature, source, operation, outcome, and target context. Do not add fallback behavior.
- Run only feature-targeted tests after each task and one checkout E2E at the end.
- Run applications, services, databases, and browser testing locally.
- The pre-implementation checkpoint is commit `0e3a103`. Do not create further Git commits without separate user approval.

---

## File Structure

### RouteDeck authoring and compilation

- Modify `routedeck_core/contracts/agent.py`: plain `AgentPolicy` declaration.
- Modify `routedeck_core/contracts/application.py`: plain `Capability`, `RouteEntry`, and `Node`; add `Node.outgoing`; define the compiled graph contract.
- Modify `routedeck_core/contracts/navigation.py`: plain route/policy names; source-implicit `Transition`; explicit `CompiledTransition`.
- Modify `routedeck_core/contracts/operations.py`: plain provider, guard, entity-input, and operation names.
- Modify `routedeck_core/contracts/surfaces.py`: plain affordance, private-form, surface, and slot names.
- Modify `routedeck_core/contracts/suggestions.py`: plain suggested-action names.
- Modify `routedeck_core/contracts/__init__.py`: publish only the clean-break names.
- Modify `routedeck_core/app/feature.py`: `Feature` and `Application` manifests without transition collections.
- Modify `routedeck_core/app/compiler.py`: collect node-owned outgoing transitions, materialize compiled transitions, derive incoming adjacency, and compile the selected features.
- Modify `routedeck_core/app/compiler_registry.py`: use the new manifest and declaration types.
- Modify `routedeck_core/app/compiler_validation.py`: validate compiled transitions and remove feature-local edge restrictions.
- Modify `routedeck_core/app/route_entries.py`: materialize route-entry self-branches as `CompiledTransition` values.
- Modify `routedeck_core/app/compiled.py`: expose `CompiledApplication`, `.application`, and `.graph`.
- Modify `routedeck_core/app/bindings.py`: expose `BoundApplication`, `ContextProviderHandler`, and `GuardHandler`.
- Modify `routedeck_core/app/frontend_contract.py`: consume compiled transitions.
- Modify `routedeck_core/app/executable_paths.py`: consume compiled transitions.
- Modify `routedeck_core/app/__init__.py` and `routedeck_core/__init__.py`: publish the clean public API.
- Modify current RouteDeck runtime consumers under `routedeck_core/`, `routedeck_fastapi/`, `routedeck_langgraph/`, `routedeck_sqlalchemy/`, `routedeck_testing/`, and `scripts/export_contracts.py`: replace old type and `.spec`/`.source_spec` names without changing behavior.

### Medusa feature declarations

- Create `examples/medusa-agent/backend/medusa_agent/features/catalog/declarations.py`: stable catalog node refs and catalog declarations consumed by other features.
- Create `examples/medusa-agent/backend/medusa_agent/features/cart/declarations.py`: stable cart node ref and cart declarations consumed by catalog.
- Create `examples/medusa-agent/backend/medusa_agent/features/checkout/declarations.py`: stable checkout node ref and checkout declarations consumed by cart.
- Create `examples/medusa-agent/backend/medusa_agent/features/orders/declarations.py`: stable confirmation ref and order declarations consumed by checkout.
- Modify each feature's `feature.py`: construct complete nodes, attach all outgoing transitions, and export `FEATURE`.
- Modify each feature's `__init__.py`: export the clean feature and declaration names.
- Modify `examples/medusa-agent/backend/medusa_agent/composition.py`: reduce it to `MEDUSA_APP` plus `compile_medusa_app()`.
- Modify `examples/medusa-agent/backend/medusa_agent/bindings.py`, `runtime.py`, `session.py`, and current backend tests: use the clean compiled/bound application API.
- Modify `examples/medusa-agent/backend/tests/contract/test_framework_imports.py`: inspect the composition root directly instead of calling a product-owned framework package inventory.

### Tests, boundary tooling, and active documentation

- Modify compiler and app tests under `tests/app/` for node-owned transitions and incoming derivation.
- Modify current tests under `tests/` and `examples/medusa-agent/backend/tests/` for the clean API names.
- Modify `routedeck_testing/factories.py`: build invalid graphs through node-owned outgoing transitions.
- Modify `scripts/check_boundaries.py`: require `FEATURE = Feature(...)` and reject legacy composition machinery.
- Modify `tests/test_public_api.py`, `tests/test_medusa_reference_slice0.py`, `tests/test_boundary_report.py`, and `tests/test_boundary_rules.py`: enforce the clean-break surface.
- Modify `README.md`, `docs/using-routedeck.md`, and `examples/medusa-agent/README.md`: teach feature-first authoring and define composition.

---

### Task 1: Replace `Spec`-Suffixed Authoring With Plain Domain Names

**Files:**
- Modify: `routedeck_core/contracts/agent.py`
- Modify: `routedeck_core/contracts/application.py`
- Modify: `routedeck_core/contracts/navigation.py`
- Modify: `routedeck_core/contracts/operations.py`
- Modify: `routedeck_core/contracts/surfaces.py`
- Modify: `routedeck_core/contracts/suggestions.py`
- Modify: `routedeck_core/contracts/__init__.py`
- Modify: `routedeck_core/app/feature.py`
- Modify: `routedeck_core/app/compiled.py`
- Modify: `routedeck_core/app/bindings.py`
- Modify: `routedeck_core/app/__init__.py`
- Modify: `routedeck_core/__init__.py`
- Modify: current Python consumers under `routedeck_core/`, `routedeck_fastapi/`, `routedeck_langgraph/`, `routedeck_sqlalchemy/`, `routedeck_testing/`, `examples/medusa-agent/backend/`, `scripts/`, and `tests/`
- Test: `tests/test_public_api.py`
- Test: `tests/app/test_compiled_contract.py`

**Interfaces:**
- Consumes: The existing declarative Pydantic contracts and compiled/bound application behavior.
- Produces: `Application`, `Feature`, `Node`, `Transition`, `Operation`, `Surface`, `Capability`, `Guard`, `RecoveryPolicy`, `CompiledApplication`, and `BoundApplication` with no compatibility aliases.

- [x] **Step 1: Change the public API test to require only clean names**

```python
def test_current_core_authoring_surface_is_canonical() -> None:
    import routedeck_core
    from routedeck_core.app import (
        Application,
        CompiledApplication,
        Feature,
        bind_app,
        compile_app,
    )

    current = {
        "Application": Application,
        "CompiledApplication": CompiledApplication,
        "Feature": Feature,
        "bind_app": bind_app,
        "compile_app": compile_app,
    }
    for name, value in current.items():
        assert name in routedeck_core.__all__
        assert getattr(routedeck_core, name) is value


def test_clean_break_removes_legacy_authoring_names() -> None:
    import routedeck_core

    for name in (
        "ApplicationSpec",
        "FeatureSpec",
        "CompiledRouteDeckApp",
        "BoundRouteDeckApp",
    ):
        assert name not in routedeck_core.__all__
        assert not hasattr(routedeck_core, name)
```

- [x] **Step 2: Run the public API test and confirm the old surface fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_public_api.py -q`

Expected: FAIL because `Application`, `Feature`, and `CompiledApplication` are not exported yet.

- [x] **Step 3: Apply the clean-break rename matrix across active Python code**

```text
AgentPolicySpec -> AgentPolicy
CapabilitySpec -> Capability
RouteEntrySpec -> RouteEntry
NodeSpec -> Node
CompiledApplicationSpec -> CompiledGraph
RouteSpec -> Route
NavigationPolicySpec -> NavigationPolicy
RecoveryPolicySpec -> RecoveryPolicy
TransitionSpec -> Transition
ContextProviderSpec -> ContextProvider
EntityProviderSpec -> EntityProvider
GuardSpec -> Guard
EntityInputSpec -> EntityInput
OperationSpec -> Operation
SuggestedActionVisibilitySpec -> SuggestedActionVisibility
SuggestedActionSpec -> SuggestedAction
SurfaceAffordanceSpec -> SurfaceAffordance
PrivateFormBindingSpec -> PrivateFormBinding
SurfaceSpec -> Surface
SurfaceSlotsSpec -> SurfaceSlots
FeatureSpec -> Feature
ApplicationSpec -> Application
CompiledRouteDeckApp -> CompiledApplication
BoundRouteDeckApp -> BoundApplication
```

Rename the runtime protocols that would collide with declarations:

```python
class ContextProviderHandler(Protocol):
    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult: ...


class GuardHandler(Protocol):
    async def __call__(self, context: GuardInvocationContext) -> GuardDecision: ...
```

Rename compiled lifecycle fields and Medusa constants/functions consistently:

```text
compiled.source_spec -> compiled.application
compiled.spec -> compiled.graph
FEATURE_SPEC -> FEATURE
MEDUSA_APP_SPEC -> MEDUSA_APP
compile_medusa_app_spec -> compile_medusa_app
```

Do not retain assignments from old names to new classes.

- [x] **Step 4: Update schema document labels without changing their purpose**

```python
"contract-schema.json": {
    "application": Application.model_json_schema(),
    "compiled_graph": CompiledGraph.model_json_schema(),
    "frontend_contract": FrontendContract.model_json_schema(),
}
```

- [x] **Step 5: Run the targeted naming and compiled-contract tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_public_api.py tests/app/test_compiled_contract.py -q`

Expected: PASS with no import or schema-document regression.

- [x] **Step 6: Scan active Python sources for legacy declarations**

Run: `rg -n "class [A-Za-z0-9_]+Spec\b|ApplicationSpec|FeatureSpec|NodeSpec|TransitionSpec|CompiledRouteDeckApp|BoundRouteDeckApp|FEATURE_SPEC|MEDUSA_APP_SPEC|compile_medusa_app_spec" routedeck_core routedeck_fastapi routedeck_langgraph routedeck_sqlalchemy routedeck_testing examples/medusa-agent/backend scripts tests --glob '*.py'`

Expected: no matches.

### Task 2: Compile Node-Owned Outgoing Transitions And Derived Incoming Adjacency

**Files:**
- Modify: `routedeck_core/contracts/navigation.py`
- Modify: `routedeck_core/contracts/application.py`
- Modify: `routedeck_core/app/feature.py`
- Modify: `routedeck_core/app/compiler.py`
- Modify: `routedeck_core/app/compiler_validation.py`
- Modify: `routedeck_core/app/route_entries.py`
- Modify: `routedeck_core/app/frontend_contract.py`
- Modify: `routedeck_core/app/executable_paths.py`
- Modify: `routedeck_testing/factories.py`
- Modify: compiler consumers that read `CompiledGraph.transitions`
- Test: `tests/app/test_feature_compiler.py`
- Test: `tests/app/test_route_entry_compiler.py`

**Interfaces:**
- Consumes: Plain `Application`, `Feature`, `Node`, and `Operation` declarations from Task 1.
- Produces: `Node.outgoing: tuple[Transition, ...]`, `CompiledTransition`, `CompiledGraph.incoming`, and a compiler that accepts no feature/application transition registries.

- [x] **Step 1: Write compiler tests for source-implicit authoring and derived incoming edges**

```python
def test_node_owns_outgoing_and_compiler_derives_incoming() -> None:
    advance = Operation(
        id="test.advance",
        title="Advance",
        description="Advance once.",
        safety_class=SafetyClass.NAVIGATION,
        outcomes=("advanced",),
    )
    end = _node("test.end", "/end")
    start = _node(
        "test.start",
        "/",
        operations=(advance,),
        outgoing=(
            Transition(
                operation=advance.ref,
                outcome="advanced",
                target=end.ref,
            ),
        ),
    )
    application = Application(
        name="node-owned",
        entry_node=start.ref,
        features=(Feature(namespace="test", nodes=(start, end)),),
    )

    compiled = compile_app(application)

    edge = compiled.graph.transitions[0]
    assert edge.source == start.ref
    assert edge.target == end.ref
    assert compiled.graph.incoming[end.id] == (edge,)
    assert compiled.graph.incoming[start.id] == ()
```

Add negative tests asserting that missing targets, unavailable source operations, undeclared outcomes, and duplicate `(source, operation, outcome)` branches include `feature='test'`, source, operation, outcome, and target in the error message.

- [x] **Step 2: Run the new compiler tests and confirm the old model fails**

Run: `.venv\Scripts\python.exe -m pytest tests/app/test_feature_compiler.py -q`

Expected: FAIL because `Node.outgoing`, source-implicit `Transition`, and `CompiledGraph.incoming` do not exist.

- [x] **Step 3: Split authored and compiled transition contracts**

```python
class Transition(_FrozenContract):
    operation: OperationRef
    outcome: str = Field(min_length=1)
    target: NodeRef


class CompiledTransition(_FrozenContract):
    source: NodeRef
    operation: OperationRef
    outcome: str = Field(min_length=1)
    target: NodeRef
```

Add the authored edge to `Node`:

```python
class Node(_FrozenContract):
    # existing fields remain unchanged
    outgoing: tuple[Transition, ...] = ()
```

Remove `transitions` from `Feature` and `Application`.

- [x] **Step 4: Materialize node-owned transitions in `compile_app()`**

```python
declared_transitions = tuple(
    CompiledTransition(
        source=node.ref,
        operation=transition.operation,
        outcome=transition.outcome,
        target=transition.target,
    )
    for feature in application.features
    for node in feature.nodes
    for transition in node.outgoing
)
```

Track node ownership while collecting nodes:

```python
feature_by_node_id: dict[str, str] = {}
for feature in application.features:
    for node in feature.nodes:
        feature_by_node_id[node.id] = feature.namespace
```

Pass this map into transition validation so every structural error identifies the source feature and full branch.

- [x] **Step 5: Derive immutable incoming adjacency after transition validation**

```python
incoming_lists: dict[str, list[CompiledTransition]] = {
    node.id: [] for node in nodes
}
for transition in transitions:
    incoming_lists[transition.target.id].append(transition)
incoming = {
    node_id: tuple(edges)
    for node_id, edges in incoming_lists.items()
}
```

Store `incoming` on `CompiledGraph` beside the flat compiled transition tuple. Keep the flat tuple as the canonical serialized edge list consumed by navigation, inspection, frontend contracts, and executable path generation.

- [x] **Step 6: Preserve route-entry compilation with explicit compiled self-branches**

`RouteEntry` remains attached to its node. `_compile_route_entry_transitions()` validates it and creates this compiled edge only when the same branch is not already present:

```python
CompiledTransition(
    source=node.ref,
    operation=operation.ref,
    outcome=entry.outcome,
    target=node.ref,
)
```

- [x] **Step 7: Update invalid graph factories to mutate `Node.outgoing`**

```python
_START = Node(
    # existing declaration fields
    outgoing=(
        Transition(
            operation=_ADVANCE.ref,
            outcome="advanced",
            target=_MIDDLE.ref,
        ),
    ),
)
```

Mutations such as dangling, missing outcome, ambiguous transition, and unreachable node replace the source node's `outgoing` tuple. They do not create a feature-level edge list.

- [x] **Step 8: Run only the compiler and route-entry slice**

Run: `.venv\Scripts\python.exe -m pytest tests/app/test_feature_compiler.py tests/app/test_route_entry_compiler.py -q`

Expected: PASS, including explicit diagnostics and deterministic incoming adjacency.

### Task 3: Move Medusa Graph Assembly Into Complete Feature Nodes

**Files:**
- Create: `examples/medusa-agent/backend/medusa_agent/features/catalog/declarations.py`
- Create: `examples/medusa-agent/backend/medusa_agent/features/cart/declarations.py`
- Create: `examples/medusa-agent/backend/medusa_agent/features/checkout/declarations.py`
- Create: `examples/medusa-agent/backend/medusa_agent/features/orders/declarations.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/catalog/feature.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/cart/feature.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/checkout/feature.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/orders/feature.py`
- Modify: all four feature `__init__.py` files
- Modify: `examples/medusa-agent/backend/medusa_agent/composition.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/runtime.py`
- Modify: `examples/medusa-agent/backend/tests/contract/test_framework_imports.py`
- Modify: `tests/app/test_app_composition.py`
- Test: `tests/app/test_app_composition.py`
- Test: `tests/app/test_feature_compiler.py::test_medusa_features_compile_to_the_nine_node_graph`
- Test: `examples/medusa-agent/backend/tests/contract/test_framework_imports.py`

**Interfaces:**
- Consumes: Node-owned transitions and clean names from Tasks 1 and 2.
- Produces: Four complete Medusa `FEATURE` values and a composition root containing only `MEDUSA_APP` and `compile_medusa_app()`.

- [x] **Step 1: Replace composition-ownership tests with feature-ownership assertions**

```python
def test_composition_only_selects_features_and_entry_node() -> None:
    import medusa_agent.composition as composition

    source = inspect.getsource(composition)
    assert "model_copy" not in source
    assert "Transition(" not in source
    assert "_COMPOSED_" not in source
    assert composition.MEDUSA_APP.features == (
        catalog_feature.FEATURE,
        cart_feature.FEATURE,
        checkout_feature.FEATURE,
        orders_feature.FEATURE,
    )


def test_cross_feature_edges_are_owned_by_their_source_nodes() -> None:
    compiled = compile_medusa_app()
    edges = {
        (edge.source.id, edge.operation.id, edge.outcome, edge.target.id)
        for edge in compiled.graph.transitions
    }
    assert ("catalog.product", "cart.open", "opened", "cart.summary") in edges
    assert ("cart.summary", "checkout.start", "started", "checkout.contact") in edges
    assert (
        "checkout.review",
        "checkout.place_order",
        "order_created",
        "orders.confirmation",
    ) in edges
    assert (
        "orders.confirmation",
        "catalog.continue_shopping",
        "continued",
        "catalog.browse",
    ) in edges
```

- [x] **Step 2: Run the composition test and confirm the central assembler fails**

Run: `.venv\Scripts\python.exe -m pytest tests/app/test_app_composition.py -q`

Expected: FAIL because `composition.py` still clones and connects nodes centrally.

- [x] **Step 3: Create stable declaration leaves for the four cross-feature targets**

Each declaration module defines its stable node reference without importing a sibling feature implementation:

```python
# features/cart/declarations.py
CART_SUMMARY_REF = NodeRef(id="cart.summary")

# features/checkout/declarations.py
CHECKOUT_CONTACT_REF = NodeRef(id="checkout.contact")

# features/orders/declarations.py
ORDER_CONFIRMATION_REF = NodeRef(id="orders.confirmation")

# features/catalog/declarations.py
CATALOG_BROWSE_REF = NodeRef(id="catalog.browse")
```

Move only cross-feature reusable declarations into these leaf modules:

```text
catalog: CATALOG_PRODUCTS_PROVIDER, CONTINUE_SHOPPING, CONTINUE_SHOPPING_AFFORDANCE
cart: BUYER_MARKET_PROVIDER, CART_STATE_PROVIDER, CART_ITEMS_PROVIDER,
      CART_BINDING_PROVIDER, CART_EXISTS_GUARD, CART_ABSENT_GUARD,
      CART_CREATE, CART_ADD_ITEM, CART_OPEN, CART_CAPABILITY,
      CREATE_CART_AFFORDANCE, ADD_ITEM_AFFORDANCE, OPEN_CART_AFFORDANCE,
      VIEW_CART_ACTION, CART_CREATE_UNKNOWN_RECOVERY,
      CART_MUTATION_UNKNOWN_RECOVERY
checkout: CHECKOUT_FACTS_PROVIDER, CHECKOUT_READY_GUARD, CHECKOUT_START,
          CHECKOUT_CAPABILITY, START_CHECKOUT_AFFORDANCE
orders: ORDER_PROVIDER, RECONCILE_ORDER, RECONCILE_ORDER_AFFORDANCE
```

Feature modules import sibling `declarations` modules only. Declaration modules import no sibling feature module.

- [x] **Step 4: Construct complete catalog nodes in the catalog feature**

Fold the current `_COMPOSED_BUYER_HOME_NODE`, `_COMPOSED_CATALOG_BROWSE_NODE`, and `_COMPOSED_CATALOG_PRODUCT_NODE` fields directly into their corresponding `Node` constructors. Add source-owned outgoing branches such as:

```python
outgoing=(
    Transition(
        operation=CART_OPEN.ref,
        outcome=MedusaOutcomeType.OPENED,
        target=CART_SUMMARY_REF,
    ),
    Transition(
        operation=CART_CREATE.ref,
        outcome=MedusaOutcomeType.CREATED,
        target=CATALOG_PRODUCT_NODE_REF,
    ),
    Transition(
        operation=CART_ADD_ITEM.ref,
        outcome=MedusaOutcomeType.ADDED,
        target=CATALOG_PRODUCT_NODE_REF,
    ),
)
```

Construct product-grid and product-detail surfaces once with their complete affordance sets. Do not use `model_copy()`.

- [x] **Step 5: Construct complete cart, checkout, and orders nodes**

- `CART_NODE` includes checkout provider/guard/operation/capability/surface affordance and owns the `checkout.start -> checkout.contact` transition.
- `REVIEW_NODE` includes order recovery provider/operation/capability/affordance and owns both confirmation transitions.
- `CONFIRMATION_NODE` includes catalog provider/operation/capability/affordance and owns the continue-shopping transition.
- Existing internal catalog, cart, and checkout feature transitions move onto their source node's `outgoing` tuple.

Each feature ends in this shape:

```python
FEATURE = Feature(
    namespace="catalog",
    nodes=(BUYER_HOME_NODE, CATALOG_BROWSE_NODE, CATALOG_PRODUCT_NODE),
)
```

- [x] **Step 6: Reduce the Medusa composition root to the manifest**

```python
from routedeck_core.app import Application, CompiledApplication, compile_app

from .features.cart import FEATURE as CART_FEATURE
from .features.catalog import BUYER_HOME_NODE, FEATURE as CATALOG_FEATURE
from .features.checkout import FEATURE as CHECKOUT_FEATURE
from .features.orders import FEATURE as ORDERS_FEATURE


MEDUSA_APP = Application(
    name="medusa-buyer",
    entry_node=BUYER_HOME_NODE.ref,
    features=(
        CATALOG_FEATURE,
        CART_FEATURE,
        CHECKOUT_FEATURE,
        ORDERS_FEATURE,
    ),
)


def compile_medusa_app() -> CompiledApplication:
    return compile_app(MEDUSA_APP)


__all__ = ["MEDUSA_APP", "compile_medusa_app"]
```

Delete `framework_packages()` from composition. Update its contract test to inspect the public imports actually present in `composition.py`.

- [x] **Step 7: Run the Medusa composition slice**

Run: `.venv\Scripts\python.exe -m pytest tests/app/test_app_composition.py tests/app/test_feature_compiler.py::test_medusa_features_compile_to_the_nine_node_graph examples/medusa-agent/backend/tests/contract/test_framework_imports.py -q`

Expected: PASS; the compiled graph has nine nodes, graph parity, cross-feature edges, and no composition-time node mutation.

### Task 4: Enforce The Boundary, Refresh Active Docs, And Verify The Checkout Flow

**Files:**
- Modify: `scripts/check_boundaries.py`
- Modify: `tests/test_medusa_reference_slice0.py`
- Modify: `tests/test_boundary_report.py`
- Modify: `tests/test_boundary_rules.py`
- Modify: `README.md`
- Modify: `docs/using-routedeck.md`
- Modify: `examples/medusa-agent/README.md`
- Test: targeted boundary tests and one local Playwright checkout flow

**Interfaces:**
- Consumes: Final clean API, node-owned graph compiler, and Medusa feature manifest.
- Produces: Executable anti-drift checks, developer documentation, and end-to-end evidence that the architecture migration preserved checkout behavior.

- [x] **Step 1: Make boundary tooling recognize the new feature declaration**

Update the AST check from `FEATURE_SPEC = FeatureSpec(...)` to:

```python
is_feature_assignment = any(
    isinstance(target, ast.Name) and target.id == "FEATURE"
    for target in node.targets
)
is_feature_constructor = _call_name(node.value.func) == "Feature"
```

Add composition checks rejecting `model_copy`, `_COMPOSED_`, `Transition(...)`, and application-level `transitions=` in `medusa_agent/composition.py`.

- [x] **Step 2: Update active developer documentation**

Use this definition verbatim in `docs/using-routedeck.md`:

> Composition selects independently authored features and the entry node. RouteDeck resolves feature-owned nodes and their outgoing transitions, derives incoming transitions, validates the complete graph, and compiles it.

Show one feature node with `outgoing=(Transition(...),)` and one `Application(name=..., entry_node=..., features=...)` manifest. Remove active examples of central transition registries and all old `*Spec` names.

- [x] **Step 3: Run focused architecture and immediate-side-effect tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest `
  tests/test_public_api.py `
  tests/app/test_feature_compiler.py `
  tests/app/test_route_entry_compiler.py `
  tests/app/test_app_composition.py `
  tests/app/test_compiled_contract.py `
  tests/test_medusa_reference_slice0.py `
  tests/test_boundary_report.py `
  tests/test_boundary_rules.py `
  examples/medusa-agent/backend/tests/contract/test_framework_imports.py `
  -q
```

Expected: PASS. Do not run the unrelated full repository test suite at this stage.

- [x] **Step 4: Run static clean-break and composition scans**

Run:

```powershell
rg -n "class [A-Za-z0-9_]+Spec\b|ApplicationSpec|FeatureSpec|NodeSpec|TransitionSpec|CompiledRouteDeckApp|BoundRouteDeckApp|FEATURE_SPEC|MEDUSA_APP_SPEC|compile_medusa_app_spec" `
  routedeck_core routedeck_fastapi routedeck_langgraph routedeck_sqlalchemy `
  routedeck_testing examples/medusa-agent/backend scripts tests `
  --glob '*.py'

rg -n "model_copy|_COMPOSED_|Transition\(|transitions\s*=" `
  examples/medusa-agent/backend/medusa_agent/composition.py
```

Expected: both commands return no matches.

- [x] **Step 5: Start the approved local RouteDeck/Medusa stack and record the exact commands and smoke URLs**

Use the existing local Medusa, backend, and Vite startup procedure documented by the reference app. Confirm the health/readiness URLs before Playwright. Do not substitute test fixtures for Medusa or the configured model.

- [x] **Step 6: Run one full human-like checkout flow at 1920x1080**

From `examples/medusa-agent/e2e` run:

```powershell
pnpm test:human-checkout-video
```

Expected: the curious conversational hybrid flow reaches a real Medusa confirmation, exercises visible navgraph navigation and deep-link behavior, and produces the configured 1920x1080 video. If the real local services or configured model are unavailable, stop and report that explicit blocker rather than substituting scripted success.

- [x] **Step 7: Report the final boundary and evidence**

Report:

- RouteDeck files that now own composition and incoming derivation
- Medusa feature/declaration files that own nodes and outgoing transitions
- the final concise `composition.py`
- exact targeted test command and result count
- exact local service commands and smoke URLs
- Playwright result and absolute video path
- remaining untracked raw artifacts
- implementation changes left uncommitted pending explicit Git approval
