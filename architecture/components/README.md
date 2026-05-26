# RouteDeck Architecture Components

This folder contains focused component docs for RouteDeck areas that change
often or define public framework boundaries. The canonical subsystem table is
`../code-map.md`.

## Component Index

| Component | Purpose | Primary code owners | Tests and evidence |
| --- | --- | --- | --- |
| `core-runtime-contract.md` | Python contracts, projections, operation metadata, runtime state, and validation helpers. | `routedeck_core/*.py` | `tests/test_core_contract.py`, `tests/test_projection_contract.py`, `tests/test_runtime_store_contract.py` |
| `langgraph-adapter.md` | Optional LangGraph integration without product-specific runtime ownership. | `routedeck_langgraph/*.py` | `tests/test_langgraph_adapter.py` |
| `react-runtime-debugger.md` | React store, provider, hooks, surfaces, location state, debugger topology, and types. | `react/src/*` | `cd react && npm test` |
| `examples-and-adoption.md` | Minimal examples and product-neutral adoption path. | `examples/**/*` | Example README review, Python/React tests |
| `packaging-public-readiness.md` | Package metadata, public docs, release posture, and scrub readiness. | `pyproject.toml`, `react/package.json`, `README.md`, `docs/*` | `python -m pytest tests -q`, `cd react && npm test` |
| `skills-and-context-architecture.md` | Repo-local skills plus the generic context architecture starter kit. | `skills/**/*`, `context_architecture_bundle/**/*` | Skill self-review, bundle script help checks |

## Update Rule

If source changes match a subsystem in `../code-map.md`, update the relevant
component doc or explicitly record in closeout that the component contract is
unchanged.
