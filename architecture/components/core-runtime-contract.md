# Core Runtime Contract

## Purpose

This component owns RouteDeck's shared product-neutral kernel for both adoption
modes: application specification and compilation contracts, runtime state,
projections, operations, guards and review, surfaces, typed events, channel
filtering, validation, and dispatch result models.

## Owner Files

- `routedeck_core/app.py`
- `routedeck_core/contracts/*.py`
- `routedeck_core/state/*.py`
- `routedeck_core/supervision/*.py`
- `routedeck_core/navigation/*.py`
- `routedeck_core/projection/*.py`
- `routedeck_core/__init__.py`

## Public Interfaces

- Manifest, node, edge, action, field, policy, surface, and runtime models.
- Runtime projection and operation readiness metadata.
- Validation helpers for manifest and runtime contracts.
- Dispatch result and event contracts used by adapters and React consumers.
- Full Flow application builder/compiler contracts.
- Core Integration executor and context-provider protocols.
- Shared event identity, correlation, sequence, visibility, channel, terminal,
  and replay semantics.
- Versioned client-contract export derived from the application specification.
- `RouteDeckSessionAggregate` named actions for canonical state transitions and
  invariant enforcement.
- Coordinated backend semantics for atomic state/result/terminal-event commit.

The public `RouteDeckOperationRunner` is one product-neutral contract, while
its implementation is composed from focused lifecycle slices under
`routedeck_core/supervision/`: request orchestration, recovery, review actions,
review staging, execution, commits, and result validation. Runtime projection
builders live in `routedeck_core/runtime_projection.py`; the extensible runtime
base remains in `routedeck_core/runtime.py`.

SQLAlchemy persistence and FastAPI/SSE transport are adjacent adapters with
their own code-map rows; they do not own canonical state behavior.

## Dependent Flows

- Product adapters projecting graph state into RouteDeck state.
- React package type parity and debugger rendering.
- LangGraph adapter validation.
- LangGraph Full Flow compilation and existing-agent executor attachment.
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
- aggregate action and runtime state lifecycle assumptions
- Full Flow/Core Integration conformance
- event envelope, channel filtering, ordering, terminal, or replay behavior
