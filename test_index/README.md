# Test Index

This folder explains what RouteDeck validation protects, how to run it, and
which source subsystems it covers.

## Suite Index

| Suite | Command | Protects | Source owner |
| --- | --- | --- | --- |
| Reference guard | `python -m pytest tests/test_medusa_reference_slice0.py -q` | RouteDeck/Medusa reference boundaries, terminology authority, API-plane separation, and slice drift checks. | Packaging and public readiness; tests and validation harness. |
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

## Update Rule

When adding, renaming, or deleting tests, update this index and the matching row
in `architecture/code-map.md`. Component docs under `architecture/components/`
should explain behavior-level contracts, not copy test implementation.
