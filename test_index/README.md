# Test Index

This folder explains what RouteDeck validation protects, how to run it, and
which source subsystems it covers.

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

## Update Rule

When adding, renaming, or deleting tests, update this index and the matching row
in `architecture/code-map.md`. Component docs under `architecture/components/`
should explain behavior-level contracts, not copy test implementation.
