---
name: routedeck-feature-authoring
description: Use when designing or changing RouteDeck Application, Feature, Node, route-entry, surface, operation, provider, guard, or transition declarations.
---

# RouteDeck Feature Authoring

Develop product features locally. RouteDeck owns complete application
composition, graph validation, incoming adjacency, runtime state, and
supervision.

## Inputs

- Real user-facing locations and product-owned routes.
- Product operations and declared outcomes.
- Facts/entity allowlists required by those operations.
- Guards, review, and external-write recovery requirements.
- Product surfaces, public props, private fields, and affordances.
- Cross-feature targets and the intended application entry node.

## Authoring Sequence

1. Create one `Feature(namespace=..., nodes=...)` per product feature.
2. Declare complete `Node` objects inside that feature.
3. Put each operation/provider/guard/surface on the node where it is meaningful.
4. Put outgoing `Transition` objects on their source node. Do not create a
   second global transition table.
5. Use `RouteEntry` for dynamic public paths that must resolve through a
   supervised product operation.
6. Use `shareable` only for routes that can create/enter from public context;
   use `session_bound` for private/session-specific routes.
7. Keep real IDs in product-private bindings and expose only scoped opaque
   handles.
8. Select features and one entry node in a small `Application` composition
   root.
9. Run `compile_app(...)`; fix every duplicate, reference, route, schema,
   outcome, reachability, or recovery error.
10. Merge feature-owned `FeatureBindings` and run `bind_app(...)`; missing,
    extra, duplicate, synchronous, or malformed implementations are errors.

## Boundaries

- Product features own domain semantics, implementations, APIs, prompts, graph
  topology, and components.
- RouteDeck owns generic composition/validation, session state, supervision,
  navigation, projection, persistence ports, transport, and browser state.
- Do not construct `RouteDeckOperationRunner`, `RouteDeckNavigationRunner`,
  `RouteDeckDependencies`, or `RouteDeckLangGraphAgentDriver` in product code.
- Do not use regex/phrase routing, implicit entity scans, compatibility aliases,
  fixture product data, or fallback handlers.
- Cross-feature references must fail compilation when the target feature is not
  selected.

## Focused Checks

```powershell
python -m pytest tests/app -q
python -m pytest tests/test_public_api.py tests/test_boundary_rules.py -q
```

For a consuming product feature, add its smallest owning backend/frontend test
and immediate boundary check. Run live integration only when the changed
behavior depends on the real external source of truth.

## Output

- Feature-local declarations and bindings.
- A composition root that only selects features and entry node.
- Updated `architecture/feature-coverage.md` and owning docs if behavior or
  ownership changed.
- Focused validation result with no unsupported broader pass claim.
