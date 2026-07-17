# RouteDeck Feature-Owned Composition Design

Status: Proposed for final review
Date: 2026-07-17
Scope: Replace the current application-level graph assembly API with feature-owned nodes and RouteDeck-owned composition.
Supersedes: The feature-composition and transition-authoring portions of `2026-07-11-routedeck-medusa-agent-design.md`.

## Decision

RouteDeck owns composition mechanics. Product developers author self-contained features whose nodes declare their legal operations, surfaces, and outgoing transitions. A consuming application only selects features and identifies the entry node.

The application does not assemble, clone, patch, or connect nodes. RouteDeck collects the selected feature nodes, resolves their references, derives incoming adjacency, validates the complete graph, and compiles the runtime and public contracts.

This leaves three implementation workstreams:

1. replace declarative `*Spec` names with plain domain names
2. move transitions onto their source nodes and make RouteDeck derive incoming adjacency
3. replace consumer-owned graph assembly with RouteDeck-owned feature composition

These are one clean-break migration. No compatibility aliases or dual authoring APIs remain afterward.

## Definition Of Composition

Composition selects independently authored features and the entry node. RouteDeck resolves feature-owned nodes and their outgoing transitions, derives incoming transitions, validates the complete graph, and compiles it.

Composition does not define runtime configuration, bind handlers, create persistence, construct transport endpoints, or construct the LangGraph execution graph. Those are separate integration responsibilities.

## Goals

- Let a developer work on a product feature by authoring that feature's nodes.
- Keep each transition beside the source state and operation that can produce it.
- Make adding or removing a feature a manifest-level decision.
- Remove application-level node cloning and transition patching.
- Make the compiler the single authority for graph assembly and validation.
- Preserve a strict boundary between declarative product behavior and runtime integrations.
- Fail with precise compile errors when features do not form a valid application.

## Non-Goals

- RouteDeck does not replace LangGraph or define the model/tool execution loop.
- RouteDeck does not move product handlers, external API clients, or product data into framework code.
- Features do not gain extension-point, contribution, facet, or overlay abstractions.
- Applications do not override or mutate feature nodes during composition.
- Incoming transitions are not a second developer-authored registry.
- The migration does not preserve the old `*Spec` API through aliases.

## Authoring Vocabulary

Declarative domain objects use their domain names. The suffix `Spec` does not add useful lifecycle information and is removed.

| Current name | Clean-break name |
| --- | --- |
| `ApplicationSpec` | `Application` |
| `FeatureSpec` | `Feature` |
| `NodeSpec` | `Node` |
| `TransitionSpec` | `Transition` |
| `OperationSpec` | `Operation` |
| `SurfaceSpec` | `Surface` |
| `CapabilitySpec` | `Capability` |
| `GuardSpec` | `Guard` |
| `RecoverySpec` | `Recovery` |

Names that communicate a real lifecycle or reference distinction remain, including `NodeRef`, `OperationRef`, `CompiledApplication`, `BoundApplication`, and `PublicProjection`.

## Node-Owned Transitions

A transition is authored on its source node. Its source is therefore implicit and is not repeated in the transition value.

```python
CATALOG_PRODUCT_NODE = Node(
    id="catalog.product",
    title="Product",
    operations=(SELECT_VARIANT, ADD_TO_CART, OPEN_CART),
    surfaces=(PRODUCT_DETAIL_SURFACE,),
    outgoing=(
        Transition(
            operation=OPEN_CART.ref,
            outcome="opened",
            target=CART_SUMMARY_REF,
        ),
    ),
)
```

`Transition` contains the operation reference, the typed outcome, and a typed target `NodeRef`. It does not contain `source`. The source is the `Node` that contains it.

An outgoing transition may target a node owned by another selected feature. The target is still only a `NodeRef`; the source feature does not import or mutate the target node object.

RouteDeck derives incoming adjacency during compilation. Incoming edges are compiled graph data used for validation, inspection, navigation, and public contracts. They are not maintained by feature authors.

### Transition Invariants

For every outgoing transition, RouteDeck validates that:

- the referenced operation is available on the source node
- the outcome is declared by that operation
- the target node exists in a selected feature
- the tuple `(source node, operation, outcome)` is unique
- the target reference is well formed and unambiguous

The compiler reports errors with the owning feature, source node, operation, outcome, and target. It never guesses a target or silently drops an invalid transition.

## Feature Ownership

A feature owns its complete node declarations.

```python
CATALOG_FEATURE = Feature(
    name="catalog",
    nodes=(CATALOG_BROWSE_NODE, CATALOG_PRODUCT_NODE),
)
```

`Feature` does not have a separate `transitions` collection. Operations, surfaces, guards, recovery policies, providers, and capabilities are referenced by the nodes that use them. Runtime implementations remain separate bindings and are not embedded in the declarative feature.

A feature may publish lightweight reference declarations for cross-feature use, such as `CART_SUMMARY_REF` or an operation reference. These declarations prevent Python import cycles without creating a new composition mechanism. They expose identity only; they do not let one feature patch another feature's node.

Feature availability and runtime implementation ownership remain distinct:

- the declarative feature says which nodes and behavior exist
- bindings say which handlers, providers, and guards implement referenced behavior
- RouteDeck validates both structural compilation and binding completeness at their respective lifecycle stages

## Application Manifest

The consumer application is a static, immutable manifest:

```python
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
```

`Application` contains only its name, entry node, and selected features. It has no application-level `transitions` field and no node override or contribution mechanism.

For Medusa, `composition.py` becomes this manifest and thin compile entry point. It contains no `_COMPOSED_*` objects, `model_copy()` calls, operation/surface augmentation, transition declarations, handler bindings, runtime configuration, or graph-building algorithms.

## RouteDeck Compilation

`compile_app()` owns the complete composition pipeline:

1. collect nodes from every selected feature
2. reject duplicate feature and node identities
3. resolve the entry-node reference
4. resolve every outgoing transition target
5. validate source operation and outcome ownership
6. reject duplicate `(source, operation, outcome)` routes
7. derive incoming adjacency for every target node
8. validate routes, hierarchy, references, and graph reachability
9. produce the immutable `CompiledApplication`
10. generate the navgraph and frontend-facing contracts from that compiled result

The compiler is deterministic. The same application value produces the same compiled graph and diagnostics. Missing nodes, operations, outcomes, providers, guards, surfaces, or runtime bindings fail at the appropriate explicit validation boundary. RouteDeck does not insert defaults, synthesize nodes, or use fallback routes.

## Cross-Feature References

Cross-feature navigation is a normal node-owned transition, not an application-owned edge.

To keep Python modules acyclic, a feature may split stable declarations from concrete node construction:

```text
features/cart/
  declarations.py   # CART_SUMMARY_REF and shared public operation identities
  nodes.py           # concrete cart nodes
  feature.py         # CART_FEATURE
  bindings.py        # runtime implementations
```

This split is used only where an actual import cycle exists. It is a module-layout technique, not a `Facet`, extension registry, contribution API, or second graph. Most features should remain smaller when no split is needed.

The ownership rule remains simple: the source feature owns the transition because it owns the node on which that transition is declared. The target feature owns the target node. RouteDeck verifies that both are present in the selected application.

## Framework And Consumer Boundaries

### RouteDeck owns

- composition and graph compilation
- node and reference resolution
- incoming-adjacency derivation
- duplicate, dangling-reference, and reachability validation
- compiled navgraph, route, surface, and public-contract generation
- runtime enforcement of the compiled product interaction graph

### Feature authors own

- product interaction nodes
- each node's legal operations, surfaces, guards, capabilities, and recovery policy
- each node's outgoing transitions and typed outcomes
- feature-specific providers and runtime handler bindings in their separate binding modules
- product behavior and external-service integrations

### The consuming application owns

- which features are included
- the application entry node
- runtime configuration and adapter selection
- binding the product implementations to RouteDeck references
- constructing its LangGraph execution graph and agent behavior

The consumer does not own graph assembly. Selecting features is the only composition decision it makes.

## RouteDeck Navgraph Versus LangGraph

The RouteDeck navgraph and LangGraph execution graph remain separate.

RouteDeck models durable product interaction states: where the user is, what operations are legal, what surfaces are active, how navigation and recovery work, and which typed outcome leads to which product state.

LangGraph models per-turn agent computation: model calls, messages, tool invocation, and control flow inside the agent runtime.

A product may change its LangGraph topology without rewriting RouteDeck composition, and may change a feature's product navigation without making RouteDeck construct the LangGraph. The integration layer projects the currently compiled RouteDeck capabilities into the agent runtime; it does not merge the two graphs.

## Failure Semantics

Composition and compilation fail loudly.

- A missing cross-feature target is a compile error.
- A selected entry node that is absent is a compile error.
- A transition using an operation unavailable on its source node is a compile error.
- An undeclared operation outcome is a compile error.
- Duplicate transition keys are a compile error.
- Duplicate node identities are a compile error.
- An unreachable selected node is a compile error unless RouteDeck has an existing explicit contract that classifies it as a legal external-entry node.
- Missing runtime bindings fail binding validation; they are not converted into disabled or synthetic behavior.

Errors include enough ownership context to fix the feature directly. RouteDeck does not fall back to an alternate node, operation, provider, handler, or route.

## Clean-Break Migration

The migration has exactly three workstreams.

### 1. Plain declarative names

Rename the public declarative classes and their uses. Remove the old `*Spec` exports rather than aliasing them. Retain reference and compiled/bound lifecycle names where those words convey a real distinction.

### 2. Node-owned transitions

Add `outgoing` to `Node`, remove `source` from `Transition`, remove feature/application transition registries, and make the compiler resolve targets and derive incoming adjacency. Move every existing transition to its source node without changing the resulting graph.

### 3. RouteDeck-owned composition

Reduce each consumer composition root to an immutable `Application` manifest. Move Medusa's current node augmentation into the owning feature node declarations, eliminate application-level `model_copy()` patching, and keep runtime bindings outside composition.

The old API is removed only after the existing compiled graph has been represented by the new feature-owned declarations and parity has been verified.

## Verification And Acceptance

Testing is targeted at each workstream and its immediate side effects, followed by one full-flow check because this migration changes the complete compiled graph.

### Compiler verification

- selected features compile into the expected node and edge set
- incoming adjacency is derived from node-owned outgoing transitions
- cross-feature targets resolve without importing target node implementations
- duplicate transition keys fail with source details
- missing targets, missing source operations, and undeclared outcomes fail explicitly
- duplicate nodes and invalid entry nodes fail explicitly
- reachability results remain correct

### Boundary verification

- consumer `composition.py` contains only the application manifest and compile entry point
- consumer composition contains no `model_copy()` calls
- `Application` and `Feature` have no transitions registry
- no facet, contribution, overlay, or extension-point abstraction is introduced
- runtime handlers, providers, adapter setup, and LangGraph construction remain outside composition
- old public `*Spec` exports and compatibility aliases are absent after migration

### Medusa parity verification

- the new compiled node set matches the current expected Medusa navgraph
- every current operation/outcome route has the same source and target after migration
- generated frontend contracts and deep links retain their behavior
- focused catalog, cart, checkout, and orders tests pass after their node declarations move
- the complete checkout flow passes once at the end, including agent, surface, hybrid interaction, navgraph navigation, and deep links

### Acceptance criteria

The design is implemented when a developer can add or modify a Medusa feature by editing that feature's nodes and bindings, then include the feature in the application manifest, without editing a central transition table or patching nodes in `composition.py`. RouteDeck must either compile the complete graph deterministically or return a precise structural error.

## Final Shape

The developer-facing mental model is:

```text
Feature authors define nodes and each node's outgoing behavior.
The application selects features and an entry node.
RouteDeck composes, validates, compiles, and runs the product interaction graph.
```

There is no fourth composition concept.
