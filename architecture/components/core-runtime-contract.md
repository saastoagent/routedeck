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
- `CompiledApplication.nodes` and `require_node(...)`, the immutable compiled
  node index used by every runtime subsystem.
- Immutable application, session, operation, conversation, event, projection,
  navigation, surface, review, failure, and retention contracts.
- `RouteDeckSessionAggregate` named actions for canonical state transitions.
- `RouteDeckOperationRunner` and `RouteDeckNavigationRunner`.
- `RouteDeckRuntimeServices`, containing the bound app, store, clock, notifier,
  ID factory, one runner, navigation over that same runner, and projector.
- `RouteDeckRuntime`, adding the sensitive codec, session callbacks, optional
  configured agent driver, runtime-owned process-local conversation-run
  coordinator, callable declared-entry ensure, and explicit lifecycle.
- `RouteDeckRuntime.provision_session(...)`, the one public provisioning path
  for host-supplied session/request IDs, canonical durable creation
  fingerprinting, async factory/initializer execution, identity/version
  validation, declared entry-run attachment, and current-snapshot reload.
- `build_routedeck_runtime(...)`, which constructs the runner once, passes it
  to navigation, builds the configured projector, then creates the optional
  driver exactly once after services exist.

The coordinator owns detached tasks and transient progress while reusing the
existing durable turn lease, mutation, conversation, and restart-recovery
contracts. It does not add durable run rows, renewable leases, or a recovery
worker. It claims the durable turn before accepting a run, retains only the
latest accumulated snapshot, evicts durable terminals, bounds recent
persistence failures, and reconstructs terminal truth from mutations.

The builder never selects an alternate store, model, notifier, driver, or
cached result after a supplied dependency fails. `RouteDeckRuntime.close()`
delegates to its explicit lifecycle.

The public compiler and supervision facades orchestrate focused internal
modules; those modules are not alternate public compilers or runners.
SQLAlchemy, FastAPI/SSE, LangGraph, and React are adjacent adapters and do not
own canonical session behavior.

## Session And Lookup Invariants

Review accept/reject require a non-empty, keyword-only `session_id`. The runner
has no configured default-session field or omitted-identity path, so every
caller must pass the session identity already selected and authorized by its
host adapter.

`CompiledApplication` stores one read-only node mapping whose keys and values
must exactly match the compiled graph. `require_node(...)` is the shared
fail-closed lookup used by context, projection, navigation, and supervision;
those subsystems do not scan the graph or invent different missing-node
semantics.

Session provisioning preserves `create_for_request(...)` replay and collision
semantics. Exact request-ID replay resolves the originally journaled session
even when the host supplies a newly generated candidate session ID; a different
stored fingerprint remains `request_id_reused`. Factory identity mismatch and
initializer identity/version regression fail before any usable snapshot is
returned.

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
python -m pytest tests/app/test_compiled_contract.py tests/state/test_runtime_builder.py tests/supervision/test_review_lifecycle.py tests/context tests/projection tests/navigation -q
python scripts/check_boundaries.py --json $env:TEMP\routedeck-boundaries.json
```

The boundary report must include a passing `runtime_ownership` check; a report
file is evidence only for the run that produced it.

## Update Triggers

Update this document and `architecture/code-map.md` when changing the runtime
containers/builder, compiler facade, canonical contracts, aggregate actions,
runner/navigation sharing, projection, lifecycle, or adapter-facing ports.
