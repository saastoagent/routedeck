# Core Runtime Contract

## Purpose

This component owns RouteDeck's product-neutral interaction kernel and the
framework runtime that supplies every adapter plane. ADR-006 is the controlling
runtime-ownership decision.

## Owner Files

- `routedeck_core/app/{compiler,compiler_registry,compiler_validation,route_entries,frontend_contract,executable_paths}.py`
- `routedeck_core/contracts/*.py`
- `routedeck_core/state/*.py`
- `routedeck_core/supervision/*.py`
- `routedeck_core/navigation/*.py`
- `routedeck_core/projection/*.py`
- `routedeck_core/ports/*.py`
- `routedeck_core/runtime.py`
- `routedeck_core/runtime_defaults.py`
- `routedeck_core/__init__.py`

## Public Interfaces

- `Application`, `Feature`, `compile_app(...)`, and `bind_app(...)`.
- Immutable application, session, operation, conversation, event, projection,
  navigation, surface, review, failure, and retention contracts.
- `RouteDeckSessionAggregate` named actions for canonical state transitions.
- `RouteDeckOperationRunner` and `RouteDeckNavigationRunner`.
- `RouteDeckRuntimeServices`, containing the bound app, store, clock, notifier,
  ID factory, one runner, navigation over that same runner, and projector.
- `RouteDeckRuntime`, adding the sensitive codec, session callbacks, optional
  configured agent driver, and explicit lifecycle.
- `build_routedeck_runtime(...)`, which constructs the runner once, passes it
  to navigation, builds the configured projector, then creates the optional
  driver exactly once after services exist.

The builder never selects an alternate store, model, notifier, driver, or
cached result after a supplied dependency fails. `RouteDeckRuntime.close()`
delegates to its explicit lifecycle.

The public compiler and supervision facades orchestrate focused internal
modules; those modules are not alternate public compilers or runners.
SQLAlchemy, FastAPI/SSE, LangGraph, and React are adjacent adapters and do not
own canonical session behavior.

## Dependent Flows

- `open_sqlalchemy_routedeck_runtime(...)` opens durable resources and calls the
  core builder fail-closed.
- `RouteDeckLangGraphDriverFactory` receives the completed runtime services.
- `create_routedeck_router_from_runtime_provider(...)` derives every HTTP plane
  from one `RouteDeckRuntime`.
- Headless and React clients consume the compiled contract and canonical
  projection/events.

## Tests And Evidence

```powershell
python -m pytest tests/state/test_runtime_builder.py tests/app tests/state tests/supervision tests/projection tests/navigation -q
python scripts/check_boundaries.py --json $env:TEMP\routedeck-boundaries.json
```

The boundary report must include a passing `runtime_ownership` check; a report
file is evidence only for the run that produced it.

## Update Triggers

Update this document and `architecture/code-map.md` when changing the runtime
containers/builder, compiler facade, canonical contracts, aggregate actions,
runner/navigation sharing, projection, lifecycle, or adapter-facing ports.
