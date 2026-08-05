# Test Index

This index maps commands to the behavior they can prove. It never records a
pass result; claim success only from a current run and identify the exact lane.

All services, databases, browser automation, and release verification run on
the local Windows development machine. The protected Medusa stack uses the
local Docker engine.

## Focused Framework Gates

Run from the RouteDeck project root:

| Gate | Command | Protects |
| --- | --- | --- |
| Public API | `python -m pytest tests/test_public_api.py -q` | Sole `Application`/`Feature` compiler API, canonical exports, and absence of retired aliases/imports. |
| Hello World tutorial | `python -m pytest tests/examples/test_hello_world_example.py -q` | The checked-in zero-key tutorial compiles, binds, and prints the documented output against the current checkout. |
| Local wiki reader | `pnpm wiki:test && pnpm --filter @routedeck/wiki-site typecheck && pnpm wiki:build` | The reader loads checked-in wiki content, supports navigation/search, renders Mermaid through a pinned lazy strict client, exposes source and failures, typechecks strictly, and produces a static build without becoming a documentation authority. Live browser checks cover flowchart, sequence, and state SVG output plus mobile overflow. |
| Application compiler | `python -m pytest tests/app -q` | Feature composition, node-owned transitions, incoming derivation, invocation-source compatibility for surfaces/suggestions/routes, routes/entry bindings, frontend contract, executable paths, and fail-loud validation. |
| Context and projection | `python -m pytest tests/context tests/projection -q` | Default-deny context/projection, public/private separation, suggested actions, and recovery projection. |
| Canonical state | `python -m pytest tests/state -q` | Immutable sessions, named aggregate actions, effects, leases, ports, runtime builder/defaults, and public exports. |
| Supervision | `python -m pytest tests/supervision -q` | One runner, fail-closed invocation-source enforcement, providers/guards, idempotency, review, crash windows, external-outcome-unknown, recovery, and turn lifecycle. |
| Navigation | `python -m pytest tests/navigation -q` | Shareable/session-bound routes, resume capability, exact history identity, surface lifecycle, and navigation transactions. |
| Persistence | `python -m pytest tests/sqlalchemy tests/sqlite/test_persistent_runtime_smoke.py -q` | SQLite/PostgreSQL ORM portability, fencing, durable journals/events/blobs, reopen, and restart recovery. |
| HTTP/SSE | `python -m pytest tests/fastapi -q` | Runtime-derived routes, exact keyword-only session provisioning, current-session selection, request-aware created-session binding, operations/reviews, strict compatibility conversation SSE serialization, replay/collision, cancellation, events, forms, private/no-store agent-context inspection, and errors. |
| Detached conversation runs and entry turns | `python -m pytest tests/fastapi/test_conversation_turns.py -q` | Durable claim before acceptance, user and assistant start/attach, monotonic latest-only accumulated progress, subscriber disconnect without task cancellation, terminal eviction/reconstruction, loud persistence failure, post-commit reload, projection request identity, and once-per-session-node entry declaration. |
| Headless assistant coordination | `pnpm --dir packages/core exec vitest run --config vitest.config.ts src/conversation/assistant.test.ts` | Assistant run start/attach, accumulated progress, monotonic cursor validation, terminal proof, synchronization, interruption, and final history reload. |
| LangGraph boundary | `python -m pytest tests/test_langgraph_agent_driver.py tests/test_langgraph_model_context.py tests/test_langgraph_policy_prompt.py examples/medusa-agent/backend/tests/contract/test_agent_middleware.py -q` | Product-owned topology and base prompt, framework-owned driver, typed triggers, strict extraction, default-deny context, agent-source tool filtering, exact prompt inspection, and supervised tools. |
| Boundary rules | `python -m pytest tests/test_boundary_report.py tests/test_boundary_rules.py tests/test_anti_drift_boundaries.py tests/test_medusa_reference_slice0.py examples/medusa-agent/backend/tests/contract/test_framework_imports.py -q` | Product-neutral framework, one runtime/runner path, no Medusa generic constructors, and no direct product Store path in the browser. |
| Testing support | `python -m pytest tests/test_testing_factories.py -q` | Test doubles remain explicit and isolated from product runtime. |

Use the row matching the changed feature. Do not run the all-up suite when a
smaller owning lane proves the change and its immediate side effects.

The non-real all-up Python regression is:

```powershell
python -m pytest tests examples/medusa-agent/backend/tests --ignore=examples/medusa-agent/backend/tests/integration/real_medusa -q
```

## Frontend Gates

The workspace requires Node.js 22.13 or newer and pnpm 11.7.0.

| Gate | Command | Protects |
| --- | --- | --- |
| Headless core | `pnpm --filter @routedeck/core test` | Strict decoding, clients, SSE, bootstrap/resync, retained requests, routing/history, forms, and observable state. |
| Headless types/build | `pnpm --filter @routedeck/core typecheck` and `pnpm --filter @routedeck/core build` | Public TypeScript API and emitted package. |
| Generated transport contracts | `pnpm contracts:check` and `python -m pytest tests/test_contract_generation.py -q` | Checked-in JSON schema, generated TypeScript types, and generated runtime object descriptors match the Pydantic authority; required/optional field legality and strict additional-property posture cannot drift silently. Core decoder tests add minimum/maximum/unknown-field payload parity, 256-code-point legacy request-ID limits, JavaScript-safe public versions, and canonical public-history empty-string behavior. |
| React | `pnpm --filter @routedeck/react test` and `pnpm --filter @routedeck/react typecheck` | Bootstrap phase/legal-action mapping, initial boundary gating, post-ready background-sync continuity, named conversation presentation, exact surface-registry validation, current-node conversation-input policy, operations, forms, review, navigation, status, and inspector primitives. |
| Testing package | `pnpm --filter @routedeck/testing test` | Explicit frontend test factories/harnesses. |
| Medusa frontend | `pnpm --filter @routedeck/medusa-agent test` | Framework-bound product bootstrap/recovery, active-run reconnect from the last accepted cursor, conversation restore, markdown chat, catalog/cart/checkout/order surfaces, review, routing, and reliability. |
| Medusa surface-props parity | `python -m pytest examples/medusa-agent/backend/tests/contract/test_surface_props_parity.py -q` and `pnpm --dir examples/medusa-agent/frontend exec vitest run --config vitest.config.ts src/tests/surface-props-parity.test.ts` | The same 16 valid/invalid vectors agree across compiled backend schemas and eight corresponding product frontend decoders. |
| Medusa type/build | `pnpm --filter @routedeck/medusa-agent typecheck` and `pnpm --filter @routedeck/medusa-agent build` | Product/public contract integration and production bundle. |

Root `pnpm test`, `pnpm typecheck`, and `pnpm build` are all-package gates.
Root Vitest discovery is package-scoped; Playwright E2E is not part of unit
coverage.

## Documentation And Architecture Gates

```powershell
python scripts/check_doc_coverage.py
python scripts/check_context_architecture.py
python -m pytest tests/test_active_design_authority.py tests/test_public_api.py tests/test_medusa_reference_slice0.py -q
```

- `check_doc_coverage.py` scans all maintained live source by default and maps
  it to `architecture/code-map.md`. Use `--files <paths...>` for a focused list
  and `--verbose` for owner/anchor detail. It never invokes Git. This proves
  file ownership coverage, not semantic implementation coverage.
- `check_context_architecture.py` verifies required canonical documents, local
  Markdown links, and absence of retired API/architecture language from the
  active documentation set. It excludes historical/archive and generated
  material.
- The focused tests lock public API, current authority, generic endpoint, and
  product/framework reference boundaries.
- A change spanning multiple owners also requires a verified semantic crosswalk
  under `knowledgebase/` that links implemented behavior, framework source,
  consumer source, canonical contracts, and focused proof. Review that crosswalk
  with the feature matrix; no single automated check substitutes for both.

Regenerate contracts when Python contract meaning or generated runtime metadata
changed, then verify the checked-in outputs without rewriting them:

```powershell
pnpm contracts:generate
pnpm contracts:check
```

Generated output is not a substitute for compiler/decoder tests.

## Runtime Ownership Report

```powershell
python scripts/check_boundaries.py --json $env:TEMP\routedeck-boundaries.json
```

The schema-4 report must include a passing `runtime_ownership` result proving
one framework-built runner/navigation path, runtime-derived transport, no
product generic constructors, and no product `astream_events(...)` calls. The
JSON also proves the product frontend does not directly own assistant-stream
event handling and that generic production source contains no buyer-specific
vocabulary. It is evidence only for that invocation.

The schema-4 scanner does not itself prove product surface-schema/decoder parity
or product-integrity algorithms. The separate shared-vector parity gate proves
the eight named Medusa decoders, and the contact-identity unit lane proves the
shared fingerprint. A green schema-4 report supports only its structural
separation checks, not every possible product contract.

## Protected Real Medusa Gate

Provision and start the local stack only when real commerce proof is in scope:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Provision
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Up -Services all
python -m pytest examples/medusa-agent/backend/tests/integration/real_medusa -q
```

Smoke URLs:

- frontend: `http://127.0.0.1:5198`
- agent API: `http://127.0.0.1:8098`
- Medusa: `http://127.0.0.1:9100`

The test must use the configured real Store API on `http://127.0.0.1:9100`.
Fixtures, synthetic catalog data, browser Store calls, alternate providers, or
canned responses invalidate the lane.

Stop without deleting protected volumes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Down
```

`Reset` is destructive and requires separate explicit authorization.

## Targeted Browser Gates

Use the Playwright story matching the feature. The high-quality synthetic
address-bar checkout recording is:

```powershell
$env:ROUTEDECK_MODEL_MODE = "live"
$env:ROUTEDECK_E2E_VIDEO = "on"
$env:ROUTEDECK_PRESENTATION_RECORDING = "1"
$env:ROUTEDECK_E2E_ARTIFACTS = "<absolute artifact directory>"
pnpm --filter @routedeck/medusa-agent-e2e exec playwright test --config live-checkout-video.playwright.config.ts human-checkout-flow.spec.ts
```

It requires the protected stack and a valid configured `OPENAI_API_KEY`. The
story must use actual Medusa data and live model mode; missing access is a
blocker. A test-only scripted graph cannot satisfy live acceptance.

Do not claim the checkout passed or a video is current from this index. Report
the exact Playwright result and retained absolute artifact path.

## Release Gate

The non-destructive package-candidate lane is:

```powershell
python -m pytest tests/test_release_harness.py tests/test_release_archives.py tests/test_public_api.py -q
python -m build --outdir "$env:TEMP\routedeck-python-dist"
pnpm build
pnpm --dir packages/core pack --pack-destination "$env:TEMP\routedeck-npm-dist"
pnpm --dir packages/react pack --pack-destination "$env:TEMP\routedeck-npm-dist"
python scripts/verify_release_archives.py --python-wheel <wheel> --npm <core-tarball> --npm <react-tarball>
```

This proves archive shape only when run against freshly built paths. A separate
temporary venv and temporary npm consumer must install those exact artifacts
to prove consumption. Neither lane proves real Medusa, browser, model, registry,
or publication behavior.

`examples/medusa-agent/scripts/release-verify.ps1` is the consolidated local
release harness. It covers framework correctness, boundaries, real commerce,
browser experience, critical coverage groups, packaging, and sanitized
evidence.

It requires explicit destructive reset intent:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\release-verify.ps1 -ResetProtectedDemo
```

Do not run it as an ordinary smoke test. Missing real dependencies or model
credentials fail the gate rather than selecting fixture/fallback behavior.

## Update Rule

When a test, command, source-of-truth requirement, or supported claim moves,
update this index, the owning feature-coverage row, and the relevant code-map
row/component contract.
