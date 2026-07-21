# Structure - RouteDeck

Last updated: 2026-07-21

```text
routedeck/
  routedeck_core/
    app/                 # Application/Feature compilation and exact bindings
    contracts/           # immutable public contracts
    context/             # operation/model scopes and framework policies
    navigation/          # routes, deep links, exact history transactions
    ports/               # executor/store/notifier/codec/clock/driver ports
    projection/          # default-deny and configured public projection
    state/               # canonical session aggregate and named actions
    supervision/         # turns, guards, review, outcomes, recovery, runner
    runtime.py           # one services/runtime builder and lifecycle
  routedeck_sqlalchemy/
    application_runtime.py # fail-closed persistent runtime opener
    store.py             # canonical store facade
    store_parts/         # focused transactional responsibilities
    ...                  # ORM, repositories, codec, lease, recovery
  routedeck_fastapi/
    router.py            # one /api/routedeck router composition
    routes/              # contract/session/operation/conversation/event/form/inspect
    conversation_*.py    # replay/projection/stream lifecycle
    runtime.py           # dependency derivation from one runtime
  routedeck_langgraph/   # generic driver, context, prompt, conversation, tools
  routedeck_testing/     # Python test-only support
  packages/
    core/                # public npm metadata, README, and clean build config
      src/               # strict browser contracts/clients/store/routing/forms
        conversation/assistant.ts # reusable assistant-only convergence
    react/               # public React metadata, README, and clean build config
      src/               # provider/hooks/conversation/surfaces/review/Navgraph
    testing/             # private frontend test harnesses
  examples/medusa-agent/
    backend/medusa_agent/
      features/          # catalog/cart/checkout/orders complete feature slices
      medusa/client/     # typed Store protocol/resources/transport/wire/evidence
      composition.py     # select MEDUSA_APP features and entry node
      bindings.py        # merge feature-owned product implementations
      session.py         # buyer market/session callbacks
      agent.py           # product prompts/models/LangGraph graphs
      contact_identity.py # shared checkout/order contact identity
      runtime.py         # strict product inputs to framework opener
    backend/main.py      # product host: runtime provider, generic router, health
    frontend/src/        # product shell, surfaces, markdown, Navgraph layout
    medusa/              # pinned real local Store server and seed declaration
    infra/               # protected Compose/sentinel/fixture ownership
    contracts/           # shared backend/frontend surface-props parity vectors
    scripts/             # stack and release tools
    e2e/                 # targeted Playwright stories and recording support
  architecture/
    feature-coverage.md  # complete feature/owner/code/doc/test matrix
    code-map.md          # machine-readable subsystem source ownership
    documentation-map.md # canonical/historical authority
    components/          # focused subsystem contracts
  docs/
    route-deck-reference.md
    using-routedeck.md
    medusa-agent-reference-app.md
    releasing.md         # local candidate vs external publication gates
    archive/             # superseded/completed historical material
  decisions/             # ADR-006 current runtime authority
  tests/                 # Python framework/boundary suites
  test_index/            # validation meaning and commands
  skills/                # live repeatable developer workflows only
  context_*/ logs/       # restart/session history
  .github/               # read-only CI, dependency updates, contribution forms
  ROADMAP.md             # directional M0-M3 outcomes, not architecture authority
  CONTRIBUTING.md, SECURITY.md, SUPPORT.md, CODE_OF_CONDUCT.md
```

## Dependency Rules

| Path | Owns | Must not own |
| --- | --- | --- |
| `routedeck_core/` | Generic compiler, contracts, state, supervision, navigation, projection, runtime, ports. | Optional adapters, product APIs/prompts/graphs/UI. |
| `routedeck_sqlalchemy/` | Explicit durable persistence and recovery behind core ports. | Product recovery policy or alternate fallback stores. |
| `routedeck_fastapi/` | Generic runtime-derived transport and guest selection adapter. | Medusa routes, product schemas, or user authorization policy. |
| `routedeck_langgraph/` | Generic graph driving/context/tool boundary. | Product topology, prompts, model selection, or wording. |
| `packages/core/` | Authoritative browser mirror and transport/routing mechanics. | React rendering or product route inference. |
| `packages/react/` | Product-neutral React primitives and read-only diagnostics. | Product components/copy/Store calls or second state authority. |
| `examples/medusa-agent/` | All commerce, Store API, product graph, market, UI, and local stack behavior. | Generic RouteDeck runtime/driver/transport construction. |

New products declare/bind features, supply session/product graph callbacks, and
call a RouteDeck runtime opener. They do not construct generic runners,
navigation, FastAPI dependencies, or the LangGraph driver.

## Non-Authority And Local-Only Paths

- `.venv/`, caches, `node_modules/`, `dist/`, and `graphify-out/` are generated.
- `artifacts/` is evidence, not current architecture.
- `codex_chats_and_memories/` is a local conversation archive outside product
  and documentation authority.
- `.env.local`, `.demo-data/`, credentials, databases, and release bundles are
  local-only and must not become product defaults.
