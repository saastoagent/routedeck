# Structure - RouteDeck

Last updated: 2026-07-14

This is the maintained ownership map for the clean-break architecture.

```text
routedeck/
  routedeck_core/
    app/                 # ApplicationSpec/FeatureSpec compilation and binding
    contracts/           # immutable public contracts
    context/             # operation-scoped context and policy lenses
    navigation/          # routes, deep links, and history transactions
    ports/               # executor, store, notifier, and clock protocols
    projection/          # default-deny public projection
    state/               # canonical session aggregate and lifecycle rules
    supervision/         # turns, guards, review, outcomes, and runner
  routedeck_sqlalchemy/  # SQLite/PostgreSQL ORM store and sensitive codec
  routedeck_fastapi/     # generic HTTP, private-form, and SSE transport
  routedeck_langgraph/   # optional context middleware and supervised tools
  routedeck_testing/     # Python test-only support
  packages/
    core/                # headless TypeScript client/store/routing/forms
    react/               # React provider, hooks, surfaces, review, navgraph
    testing/             # frontend test-only harnesses
  examples/medusa-agent/
    backend/medusa_agent/
      api/               # product chat, entry, history, and health endpoints
      features/          # catalog, cart, checkout, and order vertical slices
      medusa/client/     # typed Store API port, adapter, models, and failures
      bindings.py        # thin feature-binding composition root
      composition.py     # declarative product application composition
      runtime_factory.py # live dependency assembly
    frontend/src/
      app/               # bootstrap, chat transport, and product shell state
      features/          # buyer-facing product surfaces
      routedeck/         # framework client and surface registry seam
      ui/                # application shell and conversation UI
    medusa/              # pinned local Medusa server and declared demo seed
    infra/               # protected local Compose stack
    scripts/             # stack and release-verification tools
  tests/                 # Python framework and boundary suites
  architecture/          # subsystem ownership and component contracts
  docs/                  # framework and reference-app documentation
  decisions/             # architecture decisions
```

## Ownership Rules

| Path | Owns | Must not own |
| --- | --- | --- |
| `routedeck_core/` | Generic contracts, canonical state, supervision, projection, navigation, and ports. | Product prompts, domain APIs, commerce rules, or React components. |
| `routedeck_sqlalchemy/` | SQLAlchemy models and repositories for sessions, attempts, reviews, events, leases, private blobs, and migrations. | Product recovery policy or alternate execution paths. |
| `routedeck_fastapi/` | Generic `/api/routedeck/*` transport and typed SSE. | Medusa routes or product response schemas. |
| `routedeck_langgraph/` | Model-context filtering and supervised tool integration. | Product topology, prompts, model selection, or state authority. |
| `packages/core/` | Typed browser client, observable store, routing/history, and private-form state. | React rendering or product-specific route inference. |
| `packages/react/` | Generic React primitives over the headless runtime. | Medusa copy, cards, checkout policy, or Store API calls. |
| `packages/testing/` | Test-only frontend factories and harnesses. | Product runtime behavior or published application state. |
| `examples/medusa-agent/backend/medusa_agent/features/` | Product declarations, bindings, handlers, providers, and guards. | Generic persistence, navigation, or transport behavior. |
| `examples/medusa-agent/backend/medusa_agent/medusa/client/` | All Store endpoints, HTTP transport, wire decoding, typed results, and delivery evidence. | RouteDeck mechanics or UI rendering. |
| `examples/medusa-agent/frontend/src/features/` | Buyer-facing product components. | Direct Store API access or canonical application state. |
| `examples/medusa-agent/infra/` | Explicit local demo provisioning, Compose services, and scoped reset policy. | Production data or hidden substitute behavior. |

New applications use `ApplicationSpec`, `FeatureSpec`, `compile_app(...)`,
`FeatureBindings.merge(...)`, and `bind_app(...)`. The JavaScript framework
surface is exclusively `packages/core`, `packages/react`, and
`packages/testing`.

## Generated And Local-Only Paths

- `.venv/`, `.pytest_cache/`, `__pycache__/`, `node_modules/`, and `dist/` are
  dependency or build output.
- `artifacts/contracts/` is generated from compiled contracts.
- `examples/medusa-agent/.env.local`, `.demo-data/`, generated credentials,
  SQLite sidecars, and release bundles are local-only.
- `graphify-out/` is analysis output, not product source.
