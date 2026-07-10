# Test Index

This folder explains what RouteDeck validation protects, how to run it, and
which source subsystems it covers.

The current suites protect the transitional implementation. The active full
framework plan adds the target suites listed below; do not report them as
passing until those files exist and the commands have run.

## Suite Index

| Suite | Command | Protects | Source owner |
| --- | --- | --- | --- |
| Reference guard | `python -m pytest tests/test_medusa_reference_slice0.py -q` | RouteDeck/Medusa reference boundaries, terminology authority, API-plane separation, and slice drift checks. | Packaging and public readiness; tests and validation harness. |
| Medusa reference example focused suite | `cd examples/medusa-agent/backend && python -m pytest tests/test_medusa_catalog.py tests/test_slice1_chat.py tests/test_slice2_projection.py tests/test_slice3_projection_surfaces.py -q`; `cd examples/medusa-agent/frontend && npm test -- --run` | Medusa app-owned chat SSE, separate RouteDeck state SSE, read-only Store API catalog/media projection, planning context, literal graph, dynamic projection chips, and product-media anti-drift guards. | Medusa reference example; tests and validation harness. |
| Python contract tests | `python -m pytest tests -q` | Core contracts, projection/runtime store contracts, LangGraph adapter, and reference guards. | Core contracts and runtime state; LangGraph adapter; tests and validation harness. |
| React tests | `cd react && npm test` | React store, hooks, debugger, TypeScript-facing runtime behavior. | React runtime, store, and debugger. |
| Architecture coverage advisory | `python scripts/check_doc_coverage.py` | Changed file ownership against `architecture/code-map.md`; advisory closeout warnings. | Architecture coverage docs; tests and validation harness. |

## Current Validation Priority

For reference-only and context-only changes, run:

```powershell
python -m pytest tests/test_medusa_reference_slice0.py -q
python scripts/check_doc_coverage.py
```

For downstream source alignment, run the focused suite for the changed subsystem
plus the reference guard.

For Medusa visible-slice work, run the Medusa reference example focused suite
plus:

```powershell
python -m pytest tests/test_anti_drift_boundaries.py tests/test_medusa_reference_slice0.py -q
```

## Planned Full-Framework Validation Matrix

| Lane | Planned command | Required meaning |
| --- | --- | --- |
| Application specification | `python -m pytest tests/test_app_spec.py tests/test_surface_spec.py tests/test_client_contract.py -q` | One authoritative flow/surface/operation/event contract and versioned frontend export; invalid branches, surface drift, or duplicate frontend truth fail. |
| Interaction kernel | `python -m pytest tests/test_execution_protocol.py tests/test_session_store.py tests/test_runtime_concurrency.py tests/test_runtime_idempotency.py tests/test_review_lifecycle.py -q` | One executor path, server-authoritative state, atomic dispatch claims, version checks, interruption semantics, and review. |
| Typed events and SSE | `python -m pytest tests/events tests/test_fastapi_transport.py -q` | Typed payloads, channel/visibility isolation, sequence, persistence-before-fanout, replay, overflow, disconnect, and terminal failure. |
| Durable SQLite backend | `python -m pytest tests/sqlite -q` | Atomic dispatch claims, state/result/terminal-event outbox, process reopen, replay durability, and honest interruption behavior. |
| LangGraph modes | `python -m pytest tests/langgraph -q` | Full Flow compilation and unchanged existing-graph integration both honor public/private node separation. |
| Two-mode conformance | `python -m pytest tests/conformance -q` | Full Flow and Core Integration expose identical kernel behavior. |
| React | `cd react; npm test; npm run build` | Event ordering/dedupe/replay, stale projection rejection, server authority, and surface registry behavior. |
| Standalone examples | Run each example backend pytest suite and frontend `npm ci`, `npm test`, and `npm run build` separately. | Clean, Corpus-independent examples for both adoption modes; missing real dependencies fail loudly and test fakes stay test-only. |
| Corpus regression | Run the focused Corpus backend suite, full backend suite, frontend checks, and browser acceptance in the selected runtime location. | Corpus retains domain behavior while generic compiler/runtime/event/SSE mechanics move to RouteDeck. |

The exact task-by-task commands and file paths live in
`docs/superpowers/plans/2026-07-10-routedeck-full-stack-framework-refactor.md`.
Before any service or browser smoke, ask the user to choose local, Mac mini LAN,
or Mac mini Tailscale.

## Update Rule

When adding, renaming, or deleting tests, update this index and the matching row
in `architecture/code-map.md`. Component docs under `architecture/components/`
should explain behavior-level contracts, not copy test implementation.
