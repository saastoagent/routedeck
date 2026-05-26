# Core Runtime Contract

## Purpose

This component owns RouteDeck's product-neutral Python contract: manifests,
runtime state, projections, operations, surfaces, events, validation, and
dispatch result models.

## Owner Files

- `routedeck_core/models.py`
- `routedeck_core/runtime.py`
- `routedeck_core/validation.py`
- `routedeck_core/__init__.py`

## Public Interfaces

- Manifest, node, edge, action, field, policy, surface, and runtime models.
- Runtime projection and operation readiness metadata.
- Validation helpers for manifest and runtime contracts.
- Dispatch result and event contracts used by adapters and React consumers.

## Dependent Flows

- Product adapters projecting graph state into RouteDeck state.
- React package type parity and debugger rendering.
- LangGraph adapter validation.
- Minimal examples and SaaStoAgent integration.

## Tests And Evidence

- `tests/test_core_contract.py`
- `tests/test_projection_contract.py`
- `tests/test_runtime_store_contract.py`
- `python -m pytest tests -q`

## Update Triggers

Update this doc and `architecture/code-map.md` when changing:

- model names, fields, or defaults
- validation semantics
- operation readiness metadata
- projection shape
- event or dispatch result contracts
- runtime state lifecycle assumptions
