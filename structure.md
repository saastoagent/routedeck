# Structure - RouteDeck

Last updated: 2026-07-12

This is a maintained ownership map, not a recursive file listing.

```text
routedeck/
  README.md
  pyproject.toml
  package.json
  pnpm-workspace.yaml
  routedeck_core/
    app/                 # ApplicationSpec/FeatureSpec compilation and binding
    contracts/           # immutable public contracts
    context/             # operation-scoped context
    navigation/          # routes, deep links, exact history transactions
    ports/               # executor, store, notifier, clock protocols
    projection/          # default-deny public projection
    state/               # canonical session reducers and lifecycle rules
    supervision/         # turns, guards, review, outcomes, operation runner
  routedeck_sqlite/      # durable single-host store and sensitive codec
  routedeck_fastapi/     # generic HTTP and SSE transport
  routedeck_langgraph/   # optional middleware and supervised tool adapter
  routedeck_testing/     # Python conformance and test-only support
  packages/
    core/                # headless TypeScript client/store/routing/forms
    react/               # React provider, hooks, surfaces, review, navigation
    testing/             # frontend test harnesses
  react/                 # deprecated Corpus-only compatibility package
  examples/
    medusa-agent/
      backend/
        medusa_agent/
          api/           # product chat and health endpoints
          features/      # catalog, cart, checkout, order business slices
          medusa/client/ # typed Store API port, adapter, models, failures
          composition.py # feature and dependency composition root
          runtime.py     # live RouteDeck/Medusa application assembly
      frontend/
        src/app/         # bootstrap and RouteDeck client composition
        src/features/    # product-owned buyer surfaces
        src/routedeck/   # framework client and surface registry seam
        src/ui/          # application shell and chat UI
      medusa/             # pinned repo-local Medusa server and canonical seed
      infra/             # protected local Compose stack and seed contract
      scripts/           # protected stack and release verification tools
  tests/                 # Python framework and boundary suites
  architecture/          # subsystem ownership and component contracts
  docs/                  # framework and reference-app documentation
  scripts/               # contract, coverage, and documentation tooling
  test_index/            # validation command index
  decisions/             # architecture decisions
```

## Ownership Rules

| Path | Owns | Must not own |
| --- | --- | --- |
| `routedeck_core/` | Generic contracts, canonical state, supervision, projection, navigation, and ports. | Product prompts, domain APIs, commerce rules, or React product components. |
| `routedeck_sqlite/` | Durable sessions, attempts, reviews, events, leases, private blobs, migrations, and encryption. | Product recovery policy or alternate execution paths. |
| `routedeck_fastapi/` | Generic `/api/routedeck/*` transport and typed SSE. | Medusa routes or product response schemas. |
| `routedeck_langgraph/` | Model-context filtering and supervised tool-call integration. | Product graph topology, prompts, model selection, or state authority. |
| `packages/core/` | Typed browser client, store, route/history synchronization, and private-form state. | React rendering or product-specific route inference. |
| `packages/react/` | Generic React primitives over the headless runtime. | Medusa copy, product cards, checkout field policy, or Store API calls. |
| `packages/testing/` | Test-only frontend factories and component, store, and SSE harnesses. | Product runtime behavior, fallback data, or published application state. |
| `react/` | Temporary source-compatible package for the active Corpus consumer only. | New consumers, public-readiness evidence, publication, or current package ownership. |
| `examples/medusa-agent/backend/medusa_agent/features/` | Medusa business declarations, handlers, providers, and guards. | Generic persistence, navigation, or transport behavior. |
| `examples/medusa-agent/backend/medusa_agent/medusa/client/` | All Medusa Store URLs, HTTP, wire decoding, typed results, and delivery evidence. | RouteDeck runtime mechanics or UI rendering. |
| `examples/medusa-agent/frontend/src/features/` | Buyer-facing product components. | Direct Medusa Store API access or canonical app state. |
| `examples/medusa-agent/medusa/` | Pinned Medusa server build source and the explicit local demo seed. | RouteDeck framework code, buyer-agent business policy, secrets, installed dependencies, or runtime data. |
| `examples/medusa-agent/infra/` | Protected fixture provisioning, sentinel/manifest proof, Compose services, and scoped reset policy. | Production data or silent synthetic fallbacks. |

The root-level legacy manifest/runtime modules and top-level `react/` package
remain compatibility surfaces. New standalone work uses `ApplicationSpec` /
`FeatureSpec`, `compile_app(...)`, `bind_app(...)`, and the `packages/*`
workspace. Top-level `react/` cannot be deleted until the Corpus migration and
focused parity gate described in `react/README.md` are complete.

## Generated And Local-Only Paths

- `.venv/`, `.pytest_cache/`, `__pycache__/`, `node_modules/`, and `dist/` are
  dependency or build output.
- `artifacts/contracts/` is generated from the compiled application contract.
- `examples/medusa-agent/.env.local`, `.demo-data/`, generated credential and
  seed-manifest files, SQLite sidecars, and release bundles are local-only.
- `graphify-out/` is analysis output and is not product source.

Update this file when a major directory or ownership boundary moves. Update
`architecture/code-map.md` when source globs, interfaces, test anchors, or
documentation anchors change.
