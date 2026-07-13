# Test Index

This index maps validation commands to the behavior they protect. It does not
record a pass result; report a gate as passed only from a current command run or
its sanitized release bundle.

All service, database, browser, and release verification is local Windows work.
Use the protected demo stack and the local Docker engine only.

## Framework Gates

Run from the RouteDeck project directory with the project virtual environment
active:

| Gate | Command | Protects |
| --- | --- | --- |
| Public API | `python -m pytest tests/test_public_api.py -q` | Root `ApplicationSpec`/`FeatureSpec` compiler publication, package type markers, and explicit-but-unadvertised compatibility imports. |
| Application contracts | `python -m pytest tests/app -q` | Feature composition, exact route entries, transitions, frontend contract export, and fail-loud compilation. |
| Canonical state | `python -m pytest tests/state -q` | Immutable session contracts, the transaction-scoped aggregate, leases, ports, effects, and public exports. |
| Supervision | `python -m pytest tests/supervision -q` | One runner, idempotency, review, crash windows, external-outcome-unknown, recovery, and turn lifecycle. |
| Navigation | `python -m pytest tests/navigation -q` | Shareable/session-bound routes, resume capabilities, stable/ephemeral surfaces, exact history entry identity, and navigation transactions. |
| Projection | `python -m pytest tests/projection -q` | Default-deny public projection, context scope, and recovery projection. |
| Persistence | `python -m pytest tests/sqlalchemy tests/sqlite/test_persistent_runtime_smoke.py -q` | SQLAlchemy SQLite/PostgreSQL portability, reopen, fencing, durable operation/mutation journals, events/private blobs, and schema behavior. |
| HTTP/SSE | `python -m pytest tests/fastapi -q` | Generic idempotent session creation, dispatch, navigation, review, private-form, inspect, exact mutation replay, reset, and error transport. |
| LangGraph boundary | `python -m pytest tests/test_langgraph_adapter.py examples/medusa-agent/backend/tests/contract/test_agent_middleware.py -q` | Product-owned graph topology, default-deny model context, durable conversation reconstruction, and supervised tools. |
| Boundary rules | `python -m pytest tests/test_boundary_rules.py examples/medusa-agent/backend/tests/contract/test_framework_imports.py -q` | Product-neutral framework packages and Medusa-owned commerce/API behavior. |
| Full Python | `python -m pytest tests examples/medusa-agent/backend/tests -q` | Consolidated framework and product contract coverage. Real-Medusa tests require the configured local stack. |

## Frontend Gates

The workspace requires Node.js 22.13 or newer and pnpm 11.7.0. From the
RouteDeck project directory:

```powershell
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm build
```

These commands cover generated-contract decoding, event ordering, replay and
resync, authoritative store behavior, route/history reconciliation, surface
affordances, stable/ephemeral mounting, private forms, review, React hooks, the
Medusa buyer surfaces, and production builds.

Current frontend ownership is `packages/core` (`@routedeck/core`),
`packages/react` (`@routedeck/react`), and test-only `packages/testing`
(`@routedeck/testing`). For focused package checks:

```powershell
pnpm --filter @routedeck/core test
pnpm --filter @routedeck/react test
pnpm --filter @routedeck/testing test
```

Top-level `react/` is a deprecated Corpus-only compatibility tree. Its tests
may be run only as an explicitly named compatibility gate; they do not count as
current package or release-readiness evidence, and the tree remains until the
Corpus migration/removal gate in `react/README.md` is satisfied.

Root Vitest discovery is project-scoped by `vitest.config.ts`: core, React, and
testing packages run in Node, while the Medusa frontend runs in jsdom. Compiled
`dist` tests, historical `react/tests`, and Playwright E2E specs are excluded
from unit coverage and run only in their owning lanes.

For a focused Medusa UI run:

```powershell
pnpm --filter @routedeck/medusa-agent test
pnpm --filter @routedeck/medusa-agent typecheck
pnpm --filter @routedeck/medusa-agent build
```

## Real Local Commerce Gate

Before starting or mutating any protected service, the standalone packaging
lane can be checked independently:

```powershell
docker build --tag routedeck-medusa-demo-repro-check .\examples\medusa-agent\medusa
python -m pip wheel --no-deps --wheel-dir $env:TEMP\routedeck-medusa-wheel-check .\examples\medusa-agent\backend
python scripts/check_boundaries.py --json $env:TEMP\routedeck-boundaries.json
```

The Docker build installs only the repo-local locked Medusa source. The Python
wheel metadata must require `routedeck-core[fastapi,langgraph,persistence]`. The
boundary report verifies both Medusa Compose build contexts, required source
files, exact runtime pins, lockfile version, and digest-pinned Node base. These
commands do not start the server, migrate, seed, reset, or create an order.

Provision once, then start the complete protected stack:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Provision
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Up -Services all
```

The real-Medusa backend lane is:

```powershell
python -m pytest examples/medusa-agent/backend/tests/integration/real_medusa -q
```

It must use the provisioned values in `examples/medusa-agent/.env.local` and
the real Store API on `http://127.0.0.1:9100`. The lane is invalid if a fixture
client, synthetic catalog, browser-to-Medusa request, alternate provider, or
canned response substitutes for that source of truth.

The protected stack URLs are:

- Medusa: `http://127.0.0.1:9100`
- Agent API: `http://127.0.0.1:8098`
- Frontend: `http://127.0.0.1:5198`

Stop the project without deleting its volumes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Down
```

`Reset` is a separately authorized destructive gate. It validates the protected
project, volume labels, database sentinel, generated manifest, and SQLite
deletion scope before reprovisioning.

## Release Gate

`examples/medusa-agent/scripts/release-verify.ps1` is the consolidated local
release harness. It must verify, in order:

1. framework correctness;
2. boundary and adapter integrity;
3. real commerce source of truth;
4. browser, buyer-agent, and developer experience.

The harness also enforces the configured critical branch-coverage groups,
creates only sanitized evidence, and stops the scoped demo stack in a `finally`
path.

The framework coverage command excludes `integration/real_medusa`; that suite
runs once in the dedicated real-commerce gate so its order mutation begins from
the freshly reset canonical seed rather than from an earlier test-created order.

The live buyer-agent smoke requires `OPENAI_API_KEY`. Absence of that key is a
hard release-gate failure, not permission to use a scripted or fallback model.
Test-only scripted models are valid only in isolated tests. No current pass is
claimed here.

After explicitly reviewing and approving the protected reset scope, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\release-verify.ps1 -ResetProtectedDemo
```

The reset switch is mandatory because release proof includes before/after
canonical seed evidence. Do not use this command as an ordinary smoke test.

## Documentation And Contract Checks

```powershell
pnpm contracts:generate
python scripts/check_doc_coverage.py
```

The first command regenerates the Python-derived JSON schema and TypeScript
contracts; a clean release gate requires no unexplained drift afterward. The
second command is advisory ownership coverage against `architecture/code-map.md`.

## Update Rule

When a test, gate, script, or source-of-truth requirement moves, update this
index and the owning row in `architecture/code-map.md`. Keep temporary probes
and deterministic test data explicitly isolated from product paths.
