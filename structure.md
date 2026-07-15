# Structure - RouteDeck

Last updated: 2026-07-15

This is the maintained ownership map for the ADR-006 clean-break architecture.

```text
routedeck/
  routedeck_core/
    app/                 # compiler facade plus registry/validation/output modules
    contracts/           # immutable public contracts
    context/             # operation-scoped context and policy lenses
    navigation/          # routes, deep links, and history transactions
    ports/               # executor, store, notifier, codec, clock, agent-driver ports
    projection/          # default-deny and configured session projection
    state/               # canonical session aggregate and lifecycle rules
    supervision/         # turns, guards, review, outcomes, and runner facade/slices
    runtime.py           # immutable services/runtime containers and builder
    runtime_defaults.py  # UTC clock, notifier, and ID defaults
  routedeck_sqlalchemy/
    application_runtime.py # fail-closed durable runtime opener
    store.py             # canonical SqlAlchemySessionStore facade
    store_parts/         # lifecycle/session/turn/supervision/commit/event/form/maintenance transactions
  routedeck_fastapi/
    runtime.py           # runtime-provider dependency derivation
    router.py            # one canonical /api/routedeck router
    routes/              # contract/session/operation/conversation/event/form/inspection planes
  routedeck_langgraph/
    agent_driver.py      # generic graph factory and event translation
    conversation.py      # strict user/assistant turn extraction
    middleware.py        # default-deny model context
    tool_wrapper.py      # supervised product-tool bridge
  routedeck_testing/     # Python test-only support
  packages/
    core/src/
      contracts/         # strict domain decoder modules behind decode.ts
      conversation/      # history/chat/assistant-turn client contracts
      store/             # public store facade plus focused coordinators
    react/src/
      conversation/      # named presentation actions and network lifecycle hook
      ...                # provider, hooks, surfaces, review, forms, navigation, inspector
    testing/             # frontend test-only harnesses
  examples/medusa-agent/
    backend/medusa_agent/
      api/health.py      # product liveness/readiness only
      features/          # catalog, cart, checkout, and order vertical slices
      medusa/client/
        resources/       # catalog/cart/checkout/order Store resource owners
        http.py          # canonical typed facade
        transport.py     # HTTP/auth and delivery classification
        wire.py          # strict response decoding
      agent.py           # product prompts, models, and graph factories
      bindings.py        # typed product binding composition
      composition.py     # declarative product application composition
      runtime.py         # product configuration passed to framework openers
      session.py         # buyer market, session factory, and initializer
    backend/main.py      # one runtime provider, generic router, health, lifespan
    frontend/src/
      app/               # generic client bootstrap and product shell state
      features/          # buyer-facing product surfaces
      routedeck/         # framework client and surface registry seam
      ui/                # application shell and conversation UI
    medusa/              # pinned local Medusa server and declared demo seed
    infra/               # protected local Compose stack
    scripts/             # stack and release-verification tools
  tests/                 # Python framework and boundary suites
  architecture/          # subsystem ownership and component contracts
  docs/                  # framework and reference-app documentation
  decisions/             # architecture decisions; ADR-006 is current runtime authority
```

## Ownership Rules

| Path | Owns | Must not own |
| --- | --- | --- |
| `routedeck_core/` | Generic contracts, canonical state, one runtime/services builder, supervision, projection, navigation, and ports. | Product prompts, domain APIs, commerce rules, or React components. |
| `routedeck_sqlalchemy/` | Durable resource opening/lifecycle and the SQLAlchemy store facade over focused transaction services. | Product recovery policy or alternate stores after failure. |
| `routedeck_fastapi/` | One runtime-derived `/api/routedeck/*` plane, typed user/assistant conversation lifecycle, and SSE. | Medusa routes, separate dependency bundles, or product response schemas. |
| `routedeck_langgraph/` | Generic graph-set factory, typed event translation, model-context filtering, conversation extraction, and supervised tools. | Product topology, prompts, model selection, or state authority. |
| `packages/core/` | Strict contracts, typed browser clients, observable state, routing/history, private forms, and focused store coordinators. | React rendering or product-specific route inference. |
| `packages/react/` | Generic React primitives and named conversation presentation actions. | Generic reducer-shaped transition APIs, Medusa copy, cards, or Store calls. |
| `packages/testing/` | Test-only frontend factories and harnesses. | Product runtime behavior or published application state. |
| `examples/medusa-agent/backend/medusa_agent/` | Product declarations/bindings, callbacks, graphs/prompts/models, market facts, Store client, readiness, and configuration. | Generic runners, navigation, persistence construction, agent drivers, or transport routes. |
| `examples/medusa-agent/backend/medusa_agent/medusa/client/resources/` | Typed Store resource groups and endpoint-specific request/result behavior. | RouteDeck mechanics or UI rendering. |
| `examples/medusa-agent/frontend/src/features/` | Buyer-facing product components. | Direct Store API access or canonical application state. |
| `examples/medusa-agent/infra/` | Explicit local demo provisioning, Compose services, and scoped reset policy. | Production data or hidden substitute behavior. |

New applications declare and bind an app, provide session and product graph
factories, then call a RouteDeck runtime opener. Consumers do not construct
`RouteDeckOperationRunner`, `RouteDeckNavigationRunner`,
`RouteDeckDependencies`, or `RouteDeckLangGraphAgentDriver`.

## Generated And Local-Only Paths

- `.venv/`, `.pytest_cache/`, `__pycache__/`, `node_modules/`, and `dist/` are
  dependency or build output.
- `artifacts/contracts/` is generated from compiled contracts.
- `examples/medusa-agent/.env.local`, `.demo-data/`, generated credentials,
  SQLite sidecars, and release bundles are local-only.
- `graphify-out/` is analysis output, not product source.
