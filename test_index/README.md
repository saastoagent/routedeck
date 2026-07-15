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
| Public API | `python -m pytest tests/test_public_api.py -q` | The sole root `ApplicationSpec`/`FeatureSpec` compiler publication and absence of retired imports. |
| Application contracts | `python -m pytest tests/app -q` | Feature composition, exact route entries, transitions, frontend contract export, and fail-loud compilation. |
| Canonical state | `python -m pytest tests/state -q` | Immutable session contracts, the transaction-scoped aggregate, leases, ports, effects, and public exports. |
| Supervision | `python -m pytest tests/supervision -q` | One runner, idempotency, review, crash windows, external-outcome-unknown, recovery, and turn lifecycle. |
| Navigation | `python -m pytest tests/navigation -q` | Shareable/session-bound routes, resume capabilities, stable/ephemeral surfaces, exact history entry identity, and navigation transactions. |
| Projection | `python -m pytest tests/projection -q` | Default-deny public projection, context scope, and recovery projection. |
| Persistence | `python -m pytest tests/sqlalchemy tests/sqlite/test_persistent_runtime_smoke.py -q` | SQLAlchemy SQLite/PostgreSQL portability, reopen, fencing, durable operation/mutation journals, events/private blobs, and schema behavior. |
| HTTP/SSE | `python -m pytest tests/fastapi -q` | Runtime-derived transport, assistant-only/user turns, exact replay/cross-trigger collision, interruption/cancellation, sessions, dispatch, navigation, review, private forms, inspection, reset, and errors. |
| Assistant turn | `python -m pytest tests/fastapi/test_conversation_turns.py -q` | `POST /api/routedeck/conversation/assistant-turn`, no synthetic user message, shared lifecycle, replay/collision/version behavior, and production router/runtime/store integration. |
| LangGraph boundary | `python -m pytest tests/test_langgraph_agent_driver.py tests/test_langgraph_model_context.py tests/test_langgraph_policy_prompt.py examples/medusa-agent/backend/tests/contract/test_agent_middleware.py -q` | Framework-owned driver, typed user/assistant graphs, strict extraction, default-deny context, supervised tools, and product topology ownership. |
| Boundary rules | `python -m pytest tests/test_boundary_rules.py examples/medusa-agent/backend/tests/contract/test_framework_imports.py -q` | Product-neutral framework packages and Medusa-owned declarations/bindings/graphs/Store/UI behavior. |
| Runtime ownership report | `python scripts/check_boundaries.py --json $env:TEMP\routedeck-boundaries.json` | Schema 3 report with `runtime_ownership`, one framework-built runner/navigation path, runtime-derived transport, and no product generic constructors or `astream_events(...)` calls. |
| Full Python | `python -m pytest tests examples/medusa-agent/backend/tests -q` | Consolidated framework and product contract coverage. Real-Medusa tests require the configured local stack. |

## Runtime-Boundary Refactor Targeted Gates

These are the exact focused lanes for the ADR-006 runtime-boundary refactor.
They do not claim the final all-up or live acceptance has passed.

Slice 1 — framework runtime, LangGraph adapter, persistence, and immediate host:

```powershell
python -m pytest tests/state/test_runtime_builder.py tests/sqlalchemy tests/sqlite/test_persistent_runtime_smoke.py tests/test_langgraph_agent_driver.py tests/test_langgraph_model_context.py tests/test_langgraph_policy_prompt.py examples/medusa-agent/backend/tests/contract/test_runner_binding.py examples/medusa-agent/backend/tests/contract/test_home_session.py examples/medusa-agent/backend/tests/contract/test_agent_middleware.py examples/medusa-agent/backend/tests/contract/test_chat_error_logging.py examples/medusa-agent/backend/tests/integration/test_agent_chat_flow.py -q
```

Slice 2 — assistant/chat transport and named React presentation effects:

```powershell
python -m pytest tests/fastapi/test_conversation_turns.py examples/medusa-agent/backend/tests/integration/test_entry_conversation.py examples/medusa-agent/backend/tests/integration/test_agent_chat_flow.py tests/test_anti_drift_boundaries.py -q
pnpm --filter @routedeck/core test
pnpm --filter @routedeck/react typecheck
pnpm --filter @routedeck/react test
pnpm --filter @routedeck/medusa-agent exec vitest run --config vitest.config.ts src/tests/chat-client-reliability.test.ts src/tests/agent-stream-reliability.test.tsx src/tests/app-shell.test.tsx
```

Slice 3 — compiler, FastAPI router, and SQLAlchemy façade splits:

```powershell
python -m pytest tests/app tests/fastapi tests/sqlalchemy tests/sqlite/test_persistent_runtime_smoke.py tests/test_public_api.py examples/medusa-agent/backend/tests/contract/test_chat_error_logging.py examples/medusa-agent/backend/tests/integration/test_agent_chat_flow.py -q
```

Slice 4 — TypeScript decoder/store and Medusa Store-resource splits:

```powershell
pnpm --filter @routedeck/core test
pnpm --filter @routedeck/core typecheck
pnpm --filter @routedeck/core build
pnpm --filter @routedeck/medusa-agent test
python -m pytest examples/medusa-agent/backend/tests/unit/test_release_evidence.py examples/medusa-agent/backend/tests/unit/features -q
```

Slice 5 authority and executable boundary gate:

```powershell
python scripts/check_doc_coverage.py
python -m pytest tests/test_boundary_report.py tests/test_boundary_rules.py tests/test_anti_drift_boundaries.py tests/test_medusa_reference_slice0.py tests/test_release_harness.py tests/test_active_design_authority.py tests/test_public_api.py examples/medusa-agent/backend/tests/contract/test_framework_imports.py -q
python scripts/check_boundaries.py --json $env:TEMP\routedeck-boundaries.json
```

The all-up non-real regression runs once only after all five slices are
assembled:

```powershell
python -m pytest tests examples/medusa-agent/backend/tests --ignore=examples/medusa-agent/backend/tests/integration/real_medusa -q
pnpm test
pnpm typecheck
pnpm build
```

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

`packages/core`, `packages/react`, and `packages/testing` are the complete
frontend framework workspace. There is no second React test tree.

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

## Recorded Live Acceptance

The ADR-006 final browser acceptance uses the existing protected data without a
reset. It requires a valid `OPENAI_API_KEY`, the real Store API, and live model
mode; absence of any dependency is a blocker, not permission to use a scripted
graph, fixture commerce, alternate provider, or another host.

```powershell
$env:ROUTEDECK_MODEL_MODE = "live"
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Up -Services all
$env:ROUTEDECK_E2E_VIDEO = "on"
pnpm --filter @routedeck/medusa-agent-e2e exec playwright test --config playwright.config.ts --project=desktop-chromium human-checkout-flow.spec.ts
```

The single test must cover the assistant greeting, casual chat, direct product/
cart/checkout surfaces, explicit review approval, one real cart completion,
independent order reread, and confirmation, with no browser `/store/*` request
or fallback. Preserve the one generated video as
`artifacts/routedeck-runtime-boundary/human-checkout-flow.webm`, then stop
without deleting volumes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Down
```

No successful live acceptance is claimed by this index; report it only from
the current command output and retained artifact.

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
