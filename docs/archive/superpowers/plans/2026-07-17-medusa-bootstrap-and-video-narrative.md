# Medusa Bootstrap and Video Narrative Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace internal session-restoration phase copy with one neutral loading shell and record a human checkout story that proves meaningful deep links without repeatedly reloading persistence states.

**Architecture:** The frontend owns a single stable bootstrap presentation while RouteDeck continues to perform the same bootstrap, resync, recovery, and conversation convergence behavior underneath it. The E2E checkout helper keeps its existing persistence proof by default, while the recorded human story explicitly disables review and confirmation reload proofs and retains one session-bound delivery reload. The user-to-session selection boundary is documented but not implemented in this UI slice.

**Tech Stack:** React 19, TypeScript, Vitest, Playwright, Vite, RouteDeck browser store.

## Global Constraints

- Do not change RouteDeck session, recovery, checkout, or agent behavior.
- Do not add fallback behavior.
- Run only affected frontend tests, typechecks, and the single 1920x1080 human-checkout video E2E.
- Preserve persistence proof in a non-narrative E2E path.
- Do not perform git operations without a separate explicit request.

---

### Task 1: Stable bootstrap presentation

**Files:**
- Modify: `examples/medusa-agent/frontend/src/tests/bootstrap-loading.test.tsx`
- Modify: `examples/medusa-agent/frontend/src/app/BootstrapLoadingShell.tsx`
- Modify: `examples/medusa-agent/frontend/src/app/initialConversation.ts`
- Modify: `examples/medusa-agent/frontend/src/main.tsx`

**Interfaces:**
- Consumes: the existing `MedusaMark`, React root, RouteDeck bootstrap, recovery, and initial-conversation flow.
- Produces: `BootstrapLoadingShell()` with stable copy and no phase prop; `loadInitialConversation(..., { requestId? })` with no presentation callback.

- [ ] **Step 1: Write the failing loader test**

Replace the phase table with one render and assertions for `Medusa Agent` plus `Preparing your shopping experience`, and assert the old internal phase labels are absent.

- [ ] **Step 2: Run the focused test and verify it fails for the old phase-dependent component**

Run: `pnpm --filter @routedeck/medusa-agent test -- src/tests/bootstrap-loading.test.tsx`

Expected: FAIL because the component does not render the neutral copy without a phase.

- [ ] **Step 3: Implement the stable shell and remove phase plumbing**

Render `<BootstrapLoadingShell />` with fixed copy. Remove `BootstrapLoadingPhase`, `PHASE_LABELS`, `InitialConversationPhase`, `onPhase`, and phase-specific `renderLoading(...)` calls. Keep the initial shell, explicit retry shell, bootstrap/resync behavior, and recovery shell unchanged.

- [ ] **Step 4: Run the focused loader and initial-conversation tests**

Run: `pnpm --filter @routedeck/medusa-agent test -- src/tests/bootstrap-loading.test.tsx src/tests/initial-conversation.test.ts`

Expected: PASS with no warnings or failures.

### Task 2: Narrative reload policy

**Files:**
- Modify: `examples/medusa-agent/e2e/human-checkout-flow.spec.ts`
- Modify: `examples/medusa-agent/e2e/support/buyer-flow.ts`

**Interfaces:**
- Consumes: `completeGuestCheckout(page, buyer, evidence?, options?)` and the existing stage observer.
- Produces: `CheckoutFlowOptions` with `onStage(...)` and `proveCheckoutPersistence?: boolean`; omitted proof setting preserves the current review and confirmation reload checks.

- [ ] **Step 1: Write the failing narrative call site**

Pass `proveCheckoutPersistence: false` from the human story, remove its redundant product and confirmation reload blocks, and keep the delivery-stage reload proof.

- [ ] **Step 2: Run E2E typecheck and verify the new option fails before implementation**

Run: `pnpm --filter @routedeck/medusa-agent-e2e typecheck`

Expected: FAIL because `proveCheckoutPersistence` is not yet part of the helper contract.

- [ ] **Step 3: Implement the explicit E2E-only persistence option**

Rename the observer contract to `CheckoutFlowOptions`, make `onStage` optional, default `proveCheckoutPersistence` to `true`, and guard only the review-pending and confirmation reload assertions. Do not guard checkout actions, approval checks, evidence capture, or the delivery reload owned by the human-story callback.

- [ ] **Step 4: Run the E2E typecheck**

Run: `pnpm --filter @routedeck/medusa-agent-e2e typecheck`

Expected: PASS.

### Task 3: Boundary documentation and live proof

**Files:**
- Create: `docs/superpowers/specs/2026-07-17-routedeck-session-selection-boundary.md`
- Create: a timestamped artifact directory outside committed source under `artifacts/` as explicitly requested for the video deliverable.

**Interfaces:**
- Consumes: the current guest-cookie adapter and explicit RouteDeck `session_id` runtime APIs.
- Produces: an approved ownership contract for a future injectable `SessionResolver`; one 1920x1080 live E2E video and JSON report.

- [ ] **Step 1: Document guest, authenticated-user, and multi-session ownership**

State that the consumer owns identity and authorization, RouteDeck owns selected-session state, and the adapter resolves an authorized opaque handle to an explicit internal `session_id` before storage access.

- [ ] **Step 2: Run focused static verification**

Run the two package typechecks and the focused frontend tests. Confirm the human story contains one deliberate `page.reload` and no checkout-helper reload is taken when `proveCheckoutPersistence` is false.

- [ ] **Step 3: Record the single live human checkout**

Run: `$env:ROUTEDECK_E2E_ARTIFACTS='<absolute artifact directory>'; $env:ROUTEDECK_MODEL_MODE='live'; pnpm --dir examples/medusa-agent/e2e test:human-checkout-video`

Expected: one desktop Chromium test passes; video dimensions are 1920x1080; the flow reaches order confirmation; product navigation and session-bound delivery deep-link restoration are visible.
