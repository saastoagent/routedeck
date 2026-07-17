# RouteDeck Architecture Components

This folder contains focused component docs for RouteDeck areas that change
often or define public framework boundaries. The canonical subsystem table is
`../code-map.md`.

## Component Index

| Component | Purpose | Primary code owners | Tests and evidence |
| --- | --- | --- | --- |
| `core-runtime-contract.md` | Python contracts, projections, operation metadata, runtime state, and validation helpers. | `routedeck_core/**/*.py` | `tests/app`, `tests/state`, `tests/projection`, `tests/supervision` |
| `persistence-and-recovery.md` | SQLAlchemy SQLite/PostgreSQL authority, fencing, journals, encryption, retention, and restart recovery. | `routedeck_sqlalchemy/**/*.py` | `tests/sqlalchemy`, persistent runtime smoke |
| `fastapi-conversation-transport.md` | One runtime-derived generic route plane, typed conversation, SSE, forms, and inspection. | `routedeck_fastapi/**/*.py` | `tests/fastapi` |
| `langgraph-adapter.md` | Product-owned LangGraph topology with RouteDeck model context and one supervised tool path. | `routedeck_langgraph/{middleware,tool_wrapper,model_context,conversation}.py` | `tests/test_public_api.py`, `tests/test_langgraph_model_context.py`, Medusa middleware contract tests |
| `react-runtime-debugger.md` | Headless client/store plus React bindings, surfaces, navigation, review, status, and inspector. | `packages/core/src/*`, `packages/react/src/*`, `packages/testing/src/*` | Package-owned Vitest projects, `pnpm typecheck`, `pnpm build` |
| `examples-and-adoption.md` | Generic feature-first adoption sequence and example policy. | public guides and example boundary | Public API, package, and boundary checks |
| `medusa-reference-consumer.md` | Product-owned Medusa catalog/cart/checkout/order, agent, UI, stack, and E2E proof. | `examples/medusa-agent/**/*` | Example backend/frontend tests, boundary checks, protected integration and browser gates |
| `packaging-public-readiness.md` | Python and `packages/*` metadata, canonical exports, and release posture. | `pyproject.toml`, root/package `package.json` files, `README.md`, `docs/*` | focused Python public-API/app tests, package tests/builds, dry-pack checks |
| `skills-and-context-architecture.md` | Repo-local skills plus RouteDeck-local context architecture and handoff workflow. | `skills/**/*`, root context files, lifecycle folders | Skill self-review, `python scripts/check_doc_coverage.py` |

## Update Rule

If source changes match a subsystem in `../code-map.md`, update the relevant
component doc or explicitly record in closeout that the component contract is
unchanged.
