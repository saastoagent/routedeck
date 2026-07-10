# Minimal Example

Two product-neutral standalone examples are now required by
`decisions/ADR-002-two-adoption-modes-one-kernel.md`. They are separate
framework-adoption proofs and do not replace the Medusa product reference.

The previous attempted examples at `examples/minimal-langgraph-adapter` and
`examples/minimal-fastapi-react` were removed during the 2026-06-09 Medusa
recalibration because they were being used as substitutes for requested Medusa
work. The 2026-07-10 framework goal explicitly authorizes new standalone
examples with their own plans, tests, acceptance criteria, and product-neutral
boundaries.

## Required Examples

1. A Full Flow change-planning application in which RouteDeck compiles and runs
   the LangGraph-backed backend plus typed SSE and React surfaces.
2. A Core Integration document-review application whose existing/custom agent
   remains independent and is wrapped by a RouteDeck executor adapter.

Both examples must:

- remain independent of Corpus, SaaStoAgent models, and Medusa behavior
- use real user-provided input and fail loudly when a required live model is not
  configured
- keep deterministic fixtures or model doubles inside tests only
- include backend tests, frontend tests, README instructions, and smoke commands
- use the durable SQLite reference backend in the runnable path and load the
  versioned frontend contract exported from the backend application definition
- prove the shared operation, guard, event, projection, surface, and store
  contracts for their adoption mode
- stay separate from Medusa visible-slice acceptance claims

## Validation Target

```powershell
cd examples/full-flow-change-planner/backend
python -m pytest tests -q
```

```powershell
cd examples/full-flow-change-planner/frontend
npm test
```

```powershell
cd examples/core-integration-document-review/backend
python -m pytest tests -q
cd ..\frontend
npm test
```
