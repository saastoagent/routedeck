# RouteDeck Boundary Quality Fixes Closeout

Date: 2026-07-20 16:25 IST
Repository: `D:\Dev\AI Projects\routedeck`
Runtime: local Windows; protected Docker stack
Stack command:
`powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Up -Services all`
Smoke URLs: frontend `http://127.0.0.1:5198`, agent API
`http://127.0.0.1:8098`, Medusa `http://127.0.0.1:9100`

## Requested Outcome

Implement the approved seven-slice boundary/quality plan without changing
product behavior, validate each slice proportionally, run one real Medusa/live
model checkout, retain a high-quality video, and close the context architecture
according to `work_prompt.md`.

The user authorized one local closeout commit. This log and the implementation,
test, audit, architecture, context, and archive changes listed below are its
intended content. No push, deployment, branch change, merge, reset, or pull is
part of this closeout.

## Completed Work

1. Added a reusable headless assistant-only turn coordinator to
   `packages/core/src/conversation/assistant.ts`; Medusa's
   `frontend/src/app/initialConversation.ts` now owns only greeting policy,
   request identity, and buyer-facing error translation.
2. Removed implicit review session selection. Review accept/reject requires a
   non-empty keyword-only session ID throughout core, persistence, FastAPI,
   product binding, and tests.
3. Added required `RouteDeckSessionSelector` transport composition plus an
   explicit `GuestCookieSessionSelector`. Medusa's factory now supplies explicit
   instance, TTL, worker, cookie, and browser-origin policy.
4. Neutralized generic conversation copy and upgraded
   `scripts/check_boundaries.py` to schema 4 with direct product assistant-stream
   and generic product-vocabulary checks.
5. Consolidated checkout/order contact identity in
   `backend/medusa_agent/contact_identity.py`.
6. Added `CompiledApplication.nodes` and `require_node(...)`; replaced repeated
   current-node graph scans across context, projection, navigation, and
   supervision.
7. Added `contracts/surface-props-parity.json` and backend/frontend tests for 16
   valid/invalid vectors across eight product surface decoders. Removed the two
   proven-unused frontend operation mirrors.

## Changed Files And Owning Code-Map Rows

### Compiled application and interaction runtime

- `routedeck_core/app/{compiled,compiler}.py`
- `routedeck_core/context/{agent,scope}.py`
- `routedeck_core/navigation/{engine,transactions}.py`
- `routedeck_core/projection/projector.py`
- `routedeck_core/runtime.py`
- `routedeck_core/supervision/{guards,outcome_commits,outcome_results,review_actions,review_base,review_staging,runner,runner_base,runner_support}.py`
- `routedeck_core/contracts/conversation.py`
- `routedeck_sqlalchemy/application_runtime.py`
- focused tests under `tests/app`, `tests/context`, `tests/navigation`,
  `tests/projection`, `tests/sqlalchemy`, `tests/sqlite`, `tests/state`, and
  `tests/supervision`.

### FastAPI conversation and transport

- `routedeck_fastapi/{__init__,dependencies,router,runtime,session_http}.py`
- `routedeck_fastapi/routes/{conversation,operations,private_forms,sessions}.py`
- `tests/fastapi/{test_conversation_turns,test_session_selection,test_transport_smoke}.py`

### Headless TypeScript runtime and React primitives

- `packages/core/src/conversation/{assistant,assistant.test,client,codec}.ts`
- `packages/core/src/index.ts`
- `packages/react/src/conversation/useRouteDeckConversation.ts`

### Standalone Medusa reference consumer

- `examples/medusa-agent/backend/{app,main}.py`
- `examples/medusa-agent/backend/medusa_agent/{config,contact_identity,runtime}.py`
- `examples/medusa-agent/backend/medusa_agent/features/{checkout,orders}/models.py`
- related backend contract, integration, support, readiness/config/contact, and
  real-Medusa tests.
- `examples/medusa-agent/contracts/surface-props-parity.json`
- `examples/medusa-agent/frontend/src/app/initialConversation.ts`
- eight catalog/cart/checkout/order surface component files,
  `frontend/src/routedeck/identifiers.ts`, and
  `frontend/src/tests/surface-props-parity.test.ts`.
- `examples/medusa-agent/e2e/{human-checkout-flow.spec.ts,support/buyer-flow.ts}`
- `examples/medusa-agent/infra/{compose.yaml,demo-manifest.json}` and
  `examples/medusa-agent/scripts/demo-stack.ps1`.

### Validation and context governance

- `scripts/check_boundaries.py`, `tests/test_boundary_report.py`
- `docs/route-deck-reference.md`, `SYSTEM_FLOW_INDEX.md`,
  `test_index/README.md`, `examples/medusa-agent/README.md`
- `architecture/{code-map,feature-coverage}.md` and four owning component docs
- `audits/README.md` and the post-fix audit
- prior `context.md` moved to `context_history/`
- completed plan moved from `plans/` to `docs/archive/`
- new `context.md`, this log, and the final checkpoint.

Generated build/cache output and protected local database/runtime evidence are
not source owners and were not treated as implementation contracts.

## Issues Encountered

- Provisioning initially rejected an attempted `runtime_policy` addition to the
  immutable seed manifest. That field was removed; deployment policy correctly
  lives in explicit host environment configuration.
- The protected environment had no live-model key. The previously authorized
  SaaStoAgent STA key was injected into the agent-api process environment only;
  it was not printed, copied into repository source, or added to the protected
  env file.
- One live model run asked for redundant cart confirmation. The E2E story now
  answers that natural clarification if it occurs; product runtime behavior did
  not change.
- One private-form save took 13.5 seconds and the following resync exceeded a
  generic 20-second E2E assertion. The real checkout stage observation budget
  is now 60 seconds. The subsequent uninterrupted run passed.

## Validation Evidence

Focused slices passed with these observed totals:

- assistant coordination/core and Medusa wrapper: 9 and 5 tests;
- review/runtime, FastAPI transport, and Medusa binding: 57, 10, and 7 tests;
- selector/public, Medusa host, and anti-drift/static lanes: 37, 13, and 19 tests;
- schema-4 boundary lane: 12 tests and zero violations;
- contact identity lane: 11 tests;
- compiled lookup/context/projection/navigation/supervision lane: 113 checks;
- surface parity: 1 Python test and 17 frontend checks;
- core/React/Medusa/E2E typechecks, core build, and maintained Python Ruff:
  passed.

Final integration/runtime evidence:

```powershell
python -m pytest examples/medusa-agent/backend/tests/integration/real_medusa -q
# 4 passed in 21.131 seconds

$env:ROUTEDECK_MODEL_MODE = "live"
$env:ROUTEDECK_E2E_VIDEO = "on"
$env:ROUTEDECK_PRESENTATION_RECORDING = "1"
$env:ROUTEDECK_E2E_ARTIFACTS = "D:\Dev\AI Projects\routedeck\artifacts\boundary-quality-live-checkout-20260720-160830"
pnpm --filter @routedeck/medusa-agent-e2e exec playwright test --config live-checkout-video.playwright.config.ts human-checkout-flow.spec.ts
# 1 passed in 2.4 minutes
```

The passing video is 1920x1080, 25 fps, 130.84 seconds, 11,784,139 bytes:

`artifacts/boundary-quality-live-checkout-20260720-160830/raw-results/human-checkout-flow--human-7f281-th-visible-navigation-proof-desktop-chromium/video.webm`

The post-fix report is
`audits/2026-07-20-routedeck-quality-boundary-post-fix-audit.md`.

## Remaining Risk

RouteDeck supplies but does not implement a consumer's principal-aware
authenticated selector. Agent confirmation variability, one observed slow
private-form save, nine modules above 400 lines, and a not-yet-run clean public
release harness remain explicitly documented. None is hidden behind a fallback.

Final closeout checks after this log/checkpoint were present:

- `python scripts/check_doc_coverage.py` — 573 maintained files checked,
  573 mapped, 0 unmapped;
- `python scripts/check_context_architecture.py` — 41 active Markdown files,
  passed;
- `python -m pytest tests/test_active_design_authority.py tests/test_public_api.py tests/test_medusa_reference_slice0.py -q`
  — 29 passed in 13.25 seconds with one existing Pydantic deprecation warning;
- `python scripts/check_boundaries.py --json "$env:TEMP\routedeck-boundaries-final.json"`
  — schema 4, pass, zero violations.

Immediately before shutdown, frontend, agent readiness, and Medusa health each
returned HTTP 200. `demo-stack.ps1 -Action Down` then left 0 protected project
containers running and retained the protected manifest/volumes.
