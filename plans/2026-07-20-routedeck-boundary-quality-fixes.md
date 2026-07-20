# RouteDeck Boundary And Quality Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close findings QB-01 through QB-08 without moving product behavior into RouteDeck, moving framework lifecycle into Medusa, or changing the existing checkout behavior.

**Architecture:** RouteDeck owns reusable conversation coordination, explicit session-aware supervision, generic HTTP session-selection seams, compiled graph lookup, and product-neutral contracts. The Medusa consumer owns greeting policy/copy, authentication or guest selection policy, deployment values, commerce fingerprints, surface payloads/decoders, and the real checkout experience. Each slice ends with focused proof; the real Medusa/live-model checkout and video run once after all slices.

**Tech Stack:** Python 3.11+, Pydantic 2, FastAPI, SQLAlchemy, TypeScript 7, React 19, Vitest, Pytest, Playwright, pnpm.

## Global Constraints

- [ ] Preserve the clean RouteDeck/consumer boundary in ADR-006: no Medusa imports or commerce semantics in generic packages.
- [ ] Do not introduce a second runtime, runner, navigation path, conversation state machine, session truth, or fallback path.
- [ ] Do not add a dependency. The surface parity gate uses existing Python `jsonschema`, Vitest, and checked-in parity vectors.
- [ ] Do not treat authenticated identity as a RouteDeck concern. The host resolves and authorizes a principal plus opaque handle; RouteDeck receives only the selected internal session ID.
- [ ] Keep the local guest demo supported, but make its insecure HTTP cookie and local deployment values explicit at the Medusa host boundary.
- [ ] Run only the focused tests listed at the end of each slice. Do not run the full suite between slices.
- [ ] Run the protected real-Medusa/live-model checkout E2E once, after all seven slices, and retain the 1920x1080 video as final evidence.
- [ ] Do not perform Git operations unless the user separately authorizes them.
- [ ] Do not delegate work to subagents unless the user explicitly requests subagents for the implementation run.

---

## Slice 1: Move Assistant-Initiated Turn Coordination Into RouteDeck

**Resolves:** QB-01.

**Boundary result:** RouteDeck owns the generic assistant stream protocol and convergence state machine. Medusa owns only “greet when durable conversation is empty,” the stable greeting request ID, retry intent, and buyer-facing error rendering.

**Files:**

- Create: `packages/core/src/conversation/assistant.ts`
- Create: `packages/core/src/conversation/assistant.test.ts`
- Modify: `packages/core/src/index.ts`
- Modify: `examples/medusa-agent/frontend/src/app/initialConversation.ts`
- Modify: `examples/medusa-agent/frontend/src/tests/initial-conversation.test.ts`
- Modify: `architecture/components/react-runtime-debugger.md`
- Modify: `architecture/components/medusa-reference-consumer.md`
- Modify: `architecture/feature-coverage.md`

### 1.1 Protect the generic coordinator contract first

- [ ] Add failing core tests for:
  - a completed assistant turn validating request identity and both terminal frames;
  - duplicate completion, event-after-end, incomplete stream, unexpected user message, and unexpected review failure;
  - synchronization to the committed session/projection versions before conversation reload;
  - `operation_in_progress` and `version_conflict` convergence through `resync`, event observation, and durable conversation reload;
  - interrupted convergence and timeout failing loudly without silently rerunning the turn;
  - subscription-time terminal-event races not being lost.

### 1.2 Implement one product-neutral API

- [ ] Add this public shape in `assistant.ts`:

```ts
export interface AssistantInitiatedTurnOptions {
  requestId: string;
  convergenceTimeoutMs?: number;
}

export async function runAssistantInitiatedTurn(
  store: Pick<RouteDeckStore, "getState" | "subscribe" | "resync" | "synchronizeTo">,
  client: RouteDeckAgentClient,
  options: AssistantInitiatedTurnOptions,
): Promise<readonly AgentHistoryTurn[]>;
```

- [ ] Read `expected_session_version` from the RouteDeck store; do not make Medusa assemble protocol input beyond the product request ID.
- [ ] Keep generic typed error codes/messages in core. Do not mention greeting, buyer, Medusa, checkout, or commerce.
- [ ] Export the coordinator through `packages/core/src/index.ts`.

### 1.3 Reduce Medusa to product policy

- [ ] Keep `INITIAL_GREETING_REQUEST_ID` and `createGreetingRetryRequestId()` in Medusa because idempotency naming and explicit retry are product policy.
- [ ] Make `loadInitialConversation()` only:
  1. load durable conversation;
  2. return it when non-empty;
  3. invoke `runAssistantInitiatedTurn(...)` when empty.
- [ ] Remove all product-owned assistant event switches, request/version checks, convergence subscriptions, and timeout machinery.
- [ ] Keep the Medusa test focused on empty/non-empty greeting policy, stable request ID, and explicit retry ID. Move protocol cases to the new core test.

### 1.4 Focused verification

```powershell
pnpm --dir packages/core exec vitest run --config vitest.config.ts src/conversation/assistant.test.ts
pnpm --dir examples/medusa-agent/frontend exec vitest run --config vitest.config.ts src/tests/initial-conversation.test.ts
pnpm --filter @routedeck/core typecheck
pnpm --filter @routedeck/medusa-agent typecheck
```

Expected: both focused files pass; both packages typecheck; `initialConversation.ts` contains no `for await` or switch over RouteDeck assistant events.

---

## Slice 2: Make Review Session Identity Explicit And Fail Closed

**Resolves:** QB-02.

**Boundary result:** The runner executes against an already-selected session. It never guesses a user or falls back to a configured session.

**Files:**

- Modify: `routedeck_core/supervision/runner.py`
- Modify: `routedeck_core/supervision/runner_base.py`
- Modify: `routedeck_core/supervision/review_base.py`
- Modify: `routedeck_core/supervision/review_actions.py`
- Modify: `routedeck_core/runtime.py`
- Modify: `routedeck_sqlalchemy/application_runtime.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/runtime.py`
- Modify: `examples/medusa-agent/backend/tests/support/runtime.py`
- Modify: all current tests/callers returned by `rg -n "default_session_id|accept_review\(|reject_review\(" routedeck_core routedeck_sqlalchemy routedeck_testing tests examples/medusa-agent/backend`
- Modify: `architecture/components/core-runtime-contract.md`
- Modify: `SYSTEM_FLOW_INDEX.md`

### 2.1 Make omission unrepresentable

- [ ] Change `accept_review` and `reject_review` to require the keyword-only argument `session_id: str` with no default.
- [ ] Add a failing test proving an omitted argument raises Python `TypeError` before store access.
- [ ] Add a failing test proving an empty session ID is rejected explicitly and never selects another session.
- [ ] Retain cross-session review/request checks so a valid but wrong session fails closed.

### 2.2 Remove the fallback state

- [ ] Delete `default_session_id` from `RouteDeckOperationRunner`, its base/mixin contracts, runtime builders, the SQLAlchemy opener, Medusa runtime assembly, and test factories.
- [ ] Replace every legitimate review call with the exact session ID already selected by that caller.
- [ ] Delete tests that only validate the old default and replace them with explicit-session/fail-closed tests.
- [ ] Ensure FastAPI continues to pass its resolved session ID at both review endpoints.

### 2.3 Focused verification

```powershell
python -m pytest tests/supervision/test_review_lifecycle.py tests/supervision/test_durable_supervision.py tests/supervision/test_fail_closed_branches.py tests/state/test_runtime_builder.py -q
python -m pytest tests/fastapi/test_transport_smoke.py examples/medusa-agent/backend/tests/contract/test_runner_binding.py -q
rg -n "default_session_id" routedeck_core routedeck_sqlalchemy routedeck_fastapi routedeck_testing tests examples/medusa-agent/backend
```

Expected: focused tests pass; the final search returns no live source/test occurrence.

---

## Slice 3: Add An Explicit Host-Owned Session Selector And Deployment Policy

**Resolves:** QB-04 and the multi-user/session seam related to QB-02.

**Boundary result:** RouteDeck FastAPI asks an injected selector for one authorized internal session ID. Guest cookie behavior is one explicit adapter, not the definition of RouteDeck identity. Authenticated consumers can map `(principal, opaque session handle)` to an authorized session without changing RouteDeck core.

**Files:**

- Modify: `routedeck_fastapi/dependencies.py`
- Modify: `routedeck_fastapi/session_http.py`
- Modify: `routedeck_fastapi/router.py`
- Modify: `routedeck_fastapi/runtime.py`
- Modify: `routedeck_fastapi/routes/sessions.py`
- Modify: `routedeck_fastapi/routes/conversation.py`
- Modify: `routedeck_fastapi/routes/events.py`
- Modify: `routedeck_fastapi/routes/inspection.py`
- Modify: `routedeck_fastapi/routes/operations.py`
- Modify: `routedeck_fastapi/routes/private_forms.py`
- Modify: `routedeck_fastapi/__init__.py`
- Modify: `tests/fastapi/test_transport_smoke.py`
- Modify: `tests/fastapi/test_conversation_turns.py`
- Modify: `tests/test_public_api.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/config.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/runtime.py`
- Modify: `examples/medusa-agent/backend/main.py`
- Modify: `examples/medusa-agent/infra/demo-manifest.json`
- Modify: `examples/medusa-agent/README.md`
- Modify: `architecture/components/fastapi-conversation-transport.md`
- Modify: `architecture/components/medusa-reference-consumer.md`

### 3.1 Define the transport seam

- [ ] Introduce a runtime-checkable `RouteDeckSessionSelector` protocol in the FastAPI package:

```python
class RouteDeckSessionSelector(Protocol):
    async def selected_session_id(self, request: Request) -> str: ...

    def attach_created_session(
        self,
        response: Response,
        session_id: str,
    ) -> None: ...
```

- [ ] Put the selector in `RouteDeckDependencies`; replace the generic `cookie` field.
- [ ] Require a selector in `create_routedeck_router_from_runtime_provider(...)`. Do not silently construct a guest selector.
- [ ] Make all session-bound routes call the same selector exactly once per request before store access.
- [ ] Validate the selector result as a non-empty bounded string and map selection/authorization failure to one explicit HTTP problem. Do not try another identity path.

### 3.2 Keep guest mode as an explicit adapter

- [ ] Replace the free `guest_session_id`/`set_guest_cookie` pairing with `GuestCookieSessionSelector`.
- [ ] Make `GuestCookieSettings(name, secure, path)` explicit constructor values. Local Medusa must deliberately pass `secure=False`; no reusable default may imply production safety.
- [ ] Keep the cookie HTTP-only and same-site behavior explicit.
- [ ] Document that the local guest selector carries the internal ID and that a production host must use an authorization-backed opaque-handle selector.

### 3.3 Prove multi-user and multi-session composition

- [ ] Add FastAPI tests with an in-memory host selector mapping two principals and two opaque handles to distinct internal IDs.
- [ ] Prove user A cannot select user B's handle, two sessions for one user remain distinct, and review/conversation/form endpoints all use the authorized mapping.
- [ ] Keep this as a host-selector test double, not a product fallback or fake production identity provider.

### 3.4 Externalize Medusa host policy

- [ ] Add validated settings for browser origins, RouteDeck instance ID, review TTL, resume-handle TTL, worker count, guest cookie name/path/secure, with explicit protected-demo values in `demo-manifest.json` or `.env.local` provisioning.
- [ ] Remove `_DEFAULT_BROWSER_ORIGINS` and the hardcoded runtime values from `main.py`/`runtime.py`.
- [ ] Pass an explicit `GuestCookieSessionSelector` from Medusa composition.
- [ ] Fail startup when required policy is missing or malformed; do not fall back to local constants.

### 3.5 Focused verification

```powershell
python -m pytest tests/fastapi/test_transport_smoke.py tests/fastapi/test_conversation_turns.py tests/test_public_api.py -q
python -m pytest examples/medusa-agent/backend/tests/contract/test_home_session.py examples/medusa-agent/backend/tests/contract/test_runner_binding.py -q
python -m ruff check routedeck_fastapi examples/medusa-agent/backend/main.py examples/medusa-agent/backend/medusa_agent/config.py examples/medusa-agent/backend/medusa_agent/runtime.py
```

Expected: all focused tests pass; Medusa local startup configuration explicitly selects guest mode; the framework contains no implicit guest selector or insecure cookie default.

---

## Slice 4: Neutralize Framework Copy And Close The Scanner Blind Spots

**Resolves:** QB-03 and the automated blind spots for QB-01/QB-03.

**Boundary result:** Generic packages speak in RouteDeck/agent/conversation terms. Product words remain in product UI. The static report detects regressions in both ownership and vocabulary.

**Files:**

- Modify: `packages/core/src/conversation/client.ts`
- Modify: `packages/core/src/conversation/codec.ts`
- Modify: `packages/react/src/conversation/useRouteDeckConversation.ts`
- Modify: `routedeck_core/contracts/conversation.py`
- Modify: `scripts/check_boundaries.py`
- Modify: `tests/test_boundary_report.py`
- Modify: `tests/test_boundary_rules.py`
- Modify: `test_index/README.md`

### 4.1 Replace product vocabulary without changing codes

- [ ] Replace all 19 production `buyer`/`buyer-agent` occurrences in generic paths with product-neutral wording.
- [ ] Preserve error codes, classifications, state transitions, and retry semantics.
- [ ] Keep any buyer-specific translation in Medusa UI only.

### 4.2 Add static evidence

- [ ] Extend `architectural_review` evidence with:
  - product frontend direct calls to `streamAssistantTurn` or switches over generic assistant event discriminants;
  - forbidden product vocabulary in generic production files.
- [ ] Exclude tests, generated contracts, docs, and archives from production scans.
- [ ] Add isolated negative tests that create one violating file and assert the report names the exact path/line.
- [ ] Because the machine-readable evidence contract changes, bump `BOUNDARY_REPORT_SCHEMA_VERSION` from 3 to 4 once and update the report tests/documentation.

### 4.3 Focused verification

```powershell
python -m pytest tests/test_boundary_report.py tests/test_boundary_rules.py -q
python scripts/check_boundaries.py --json "$env:TEMP\routedeck-boundaries-schema4.json"
pnpm --filter @routedeck/core typecheck
pnpm --filter @routedeck/react typecheck
rg -n -i "buyer-agent|buyer data|buyer turn|buyer stream" packages/core/src packages/react/src routedeck_core --glob '!**/*.test.ts' --glob '!**/generated.ts'
```

Expected: schema 4 passes all checks; negative scanner tests prove both new detections; final vocabulary search returns no generic production occurrence.

---

## Slice 5: Consolidate The Medusa Contact Fingerprint

**Resolves:** QB-05.

**Boundary result:** Contact integrity remains product-owned, with one canonical algorithm shared by checkout and order verification.

**Files:**

- Create: `examples/medusa-agent/backend/medusa_agent/contact_identity.py`
- Create: `examples/medusa-agent/backend/tests/unit/test_contact_identity.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/checkout/models.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/orders/models.py`
- Modify: `examples/medusa-agent/backend/tests/unit/features/test_checkout.py`
- Modify: `examples/medusa-agent/backend/tests/unit/features/test_orders.py`
- Modify: `architecture/components/medusa-reference-consumer.md`

### 5.1 Pin the invariant with typed values

- [ ] Add failing tests showing Cart and Order inputs with identical email/shipping/billing values produce the same 64-character SHA-256 fingerprint.
- [ ] Cover `None` addresses, separate billing address, Unicode, and a one-field contact change.
- [ ] Assert canonical JSON options remain `ensure_ascii=False`, `allow_nan=False`, `sort_keys=True`, and compact separators.

### 5.2 Implement one canonical function

- [ ] Add one `contact_fingerprint(source: ContactFingerprintSource) -> str` function over a narrow structural protocol owned by Medusa.
- [ ] Replace `_contact_fingerprint` and `_order_contact_fingerprint`; delete both local algorithms and their duplicate imports.
- [ ] Do not move this function to RouteDeck core and do not broaden it into a generic hashing utility.

### 5.3 Focused verification

```powershell
python -m pytest examples/medusa-agent/backend/tests/unit/test_contact_identity.py examples/medusa-agent/backend/tests/unit/features/test_checkout.py examples/medusa-agent/backend/tests/unit/features/test_orders.py -q
python -m ruff check examples/medusa-agent/backend/medusa_agent/contact_identity.py examples/medusa-agent/backend/medusa_agent/features/checkout/models.py examples/medusa-agent/backend/medusa_agent/features/orders/models.py
rg -n "def _contact_fingerprint|def _order_contact_fingerprint" examples/medusa-agent/backend
```

Expected: focused tests pass and no duplicate function remains.

---

## Slice 6: Compile One Immutable Node Index And Use It Everywhere

**Resolves:** QB-07.

**Boundary result:** Compilation owns node identity and lookup. Runtime subsystems no longer implement their own linear searches or leak inconsistent `StopIteration` behavior.

**Files:**

- Modify: `routedeck_core/app/compiled.py`
- Modify: `routedeck_core/app/compiler.py`
- Modify: `routedeck_core/context/agent.py`
- Modify: `routedeck_core/context/scope.py`
- Modify: `routedeck_core/projection/projector.py`
- Modify: `routedeck_core/navigation/engine.py`
- Modify: `routedeck_core/navigation/transactions.py`
- Modify: `routedeck_core/supervision/guards.py`
- Modify: `routedeck_core/supervision/outcome_results.py`
- Modify: `routedeck_core/supervision/outcome_commits.py`
- Modify: `routedeck_core/supervision/review_staging.py`
- Modify: `tests/app/test_compiled_contract.py`
- Modify: focused context/projection/navigation/supervision tests listed below
- Modify: `architecture/components/core-runtime-contract.md`

### 6.1 Define the compiled invariant

- [ ] Add failing compiler tests proving:
  - `CompiledApplication.nodes` maps every node ID to the exact compiled node;
  - the mapping is immutable after compilation;
  - `require_node(node_id)` returns the node or raises one typed RouteDeck validation error naming the missing ID.

### 6.2 Replace local searches

- [ ] Build the immutable mapping once from the compiler's existing `node_by_id` data.
- [ ] Replace each repeated `next(... graph.nodes ...)` lookup with `CompiledApplication.require_node(...)`.
- [ ] Keep caller-specific public error mapping at navigation/transport boundaries, but never return `False` or leak `StopIteration` merely because lookup semantics differ.
- [ ] Do not add a second graph or transition registry in this slice.

### 6.3 Focused verification

```powershell
python -m pytest tests/app/test_compiled_contract.py tests/context/test_agent_context.py tests/projection/test_projector.py tests/navigation/test_engine.py tests/navigation/test_transactions.py tests/supervision/test_guards.py tests/supervision/test_fail_closed_branches.py -q
python -m ruff check routedeck_core/app routedeck_core/context routedeck_core/projection routedeck_core/navigation routedeck_core/supervision
rg -n "next\(" routedeck_core/context routedeck_core/projection routedeck_core/navigation routedeck_core/supervision
```

Expected: focused tests pass; any remaining `next(...)` occurrence is unrelated to node lookup and is documented in the slice result.

---

## Slice 7: Establish Surface Contract Parity And Remove Proven Dead Mirrors

**Resolves:** QB-06 and the actionable portion of QB-08.

**Boundary result:** The backend remains canonical for surface JSON Schema; the browser keeps strict runtime decoding; one shared valid/invalid vector set proves they agree. Only demonstrably unused constants are removed. Large files are split only when an actual invariant owner emerges during these fixes.

**Files:**

- Create: `examples/medusa-agent/contracts/surface-props-parity.json`
- Create: `examples/medusa-agent/backend/tests/contract/test_surface_props_parity.py`
- Create: `examples/medusa-agent/frontend/src/tests/surface-props-parity.test.ts`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/catalog/feature.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/cart/feature.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/checkout/feature.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/features/orders/feature.py`
- Modify/export pure decoders from:
  - `examples/medusa-agent/frontend/src/features/catalog/ProductGridSurface.tsx`
  - `examples/medusa-agent/frontend/src/features/catalog/ProductDetailSurface.tsx`
  - `examples/medusa-agent/frontend/src/features/catalog/ProductCard.tsx`
  - `examples/medusa-agent/frontend/src/features/catalog/VariantSelector.tsx`
  - `examples/medusa-agent/frontend/src/features/cart/CartSummarySurface.tsx`
  - `examples/medusa-agent/frontend/src/features/cart/CartLineItem.tsx`
  - `examples/medusa-agent/frontend/src/features/checkout/contactFormModel.ts`
  - `examples/medusa-agent/frontend/src/features/checkout/ShippingOptionsSurface.tsx`
  - `examples/medusa-agent/frontend/src/features/checkout/PaymentMethodSurface.tsx`
  - `examples/medusa-agent/frontend/src/features/checkout/OrderReviewSurface.tsx`
  - `examples/medusa-agent/frontend/src/features/orders/OrderConfirmationSurface.tsx`
- Modify: `examples/medusa-agent/frontend/src/routedeck/identifiers.ts`
- Modify: `architecture/components/medusa-reference-consumer.md`

### 7.1 Create one parity vector contract

- [ ] Add at least one valid and targeted invalid payload per public surface schema: missing required field, unexpected property, wrong primitive type, and invalid enum where applicable.
- [ ] Give every vector a stable case ID, surface ID, payload, and expected validity.
- [ ] Do not store synthetic catalog/order data in a product runtime path; this file is isolated contract-test data only.

### 7.2 Execute the same vectors on both sides

- [ ] Backend test: load the compiled Medusa application's canonical `public_props_schema` for each surface and validate every vector with existing `jsonschema` behavior.
- [ ] Frontend test: dispatch the same vector to the owning pure decoder and assert accept/reject parity.
- [ ] Export or extract pure decoder entry points only as needed for the registry; preserve rendered components and runtime validation.
- [ ] Make both tests fail with the case ID and surface ID when meanings drift.

### 7.3 Remove only proven dead code

- [ ] Delete `MedusaOperationType.CATALOG_LIST` and `MedusaOperationType.CART_OPEN`; keep the used `MedusaSurfaceType.CHECKOUT_ORDER_REVIEW` constant.
- [ ] Re-run usage search before deletion and after it.
- [ ] Do not split every module above 400 lines. Record only extractions that naturally result from the coordinator, fingerprint, resolver, or decoder ownership changes.

### 7.4 Focused verification

```powershell
python -m pytest examples/medusa-agent/backend/tests/contract/test_surface_props_parity.py -q
pnpm --dir examples/medusa-agent/frontend exec vitest run --config vitest.config.ts src/tests/surface-props-parity.test.ts
pnpm --filter @routedeck/medusa-agent typecheck
rg -n "MedusaOperationType|CATALOG_LIST|CART_OPEN" examples/medusa-agent/frontend/src
```

Expected: backend schemas and frontend decoders agree on every vector; frontend typechecks; the unused operation mirror is absent.

---

## Final Cross-Slice Gates

Run these only after Slices 1-7 are green.

### A. Static, type, and focused architecture proof

```powershell
python scripts/check_boundaries.py --json "$env:TEMP\routedeck-boundaries-final.json"
python scripts/check_doc_coverage.py
python scripts/check_context_architecture.py
python -m ruff check routedeck_core routedeck_sqlalchemy routedeck_fastapi routedeck_langgraph examples/medusa-agent/backend/medusa_agent examples/medusa-agent/backend/main.py
pnpm --filter @routedeck/core typecheck
pnpm --filter @routedeck/react typecheck
pnpm --filter @routedeck/medusa-agent typecheck
```

### B. Protected real Medusa integration

Run locally on Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Provision
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Up -Services all
python -m pytest examples/medusa-agent/backend/tests/integration/real_medusa -q
```

Smoke URLs that must be reported with their actual status:

- Frontend: `http://127.0.0.1:5198`
- Agent API: `http://127.0.0.1:8098`
- Medusa: `http://127.0.0.1:9100`

### C. One uninterrupted live-model checkout recording

```powershell
$env:ROUTEDECK_MODEL_MODE = "live"
$env:ROUTEDECK_E2E_VIDEO = "on"
pnpm --filter @routedeck/medusa-agent-e2e exec playwright test --config live-checkout-video.playwright.config.ts human-checkout-flow.spec.ts
```

- [ ] Use actual Medusa data and the configured live model; missing access is a blocker, not a reason to switch to scripted mode.
- [ ] Capture 1920x1080 with the synthetic address bar, visible deeplinks, permanently visible Navgraph, visible chat, and no reload.
- [ ] Verify one uninterrupted human-like path from general discovery through product clarification/change-of-mind, hybrid surface/chat interaction, review, order placement, confirmation, navigation, and deep-link behavior.
- [ ] Report the exact Playwright result and absolute retained video path. Do not claim success from screenshots or partial flows.
- [ ] Stop the local stack without deleting protected volumes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Down
```

---

## Documentation Closeout

- [ ] Update the owning component docs and `architecture/feature-coverage.md` only where the implemented contracts changed.
- [ ] Update `SYSTEM_FLOW_INDEX.md` and `test_index/README.md` for schema 4, explicit session selection, assistant coordinator, parity gate, and actual E2E command/evidence.
- [ ] Create a new post-fix audit rather than rewriting the historical 2026-07-20 audit.
- [ ] Follow `work_prompt.md`: retain exact validation output/artifact paths, create the closeout log/checkpoint/context-history snapshot, and refresh `context.md` to the verified post-fix state.
- [ ] Move this plan to `docs/archive/` only after every required slice and final gate is complete; until then it remains active authority under `plans/`.
