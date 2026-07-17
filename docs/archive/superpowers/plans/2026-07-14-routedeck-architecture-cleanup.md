# RouteDeck Architecture Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the clean RouteDeck/Medusa framework boundary without changing the working buyer journey.

**Architecture:** Keep RouteDeck as the single interaction-state and operation-supervision authority. Make the current compiled API unmistakable, let each Medusa feature own its runtime bindings and outcome vocabulary, keep product model roles explicitly configured, and split only files that currently mix distinct responsibilities.

**Tech Stack:** Python 3.11, Pydantic 2, LangGraph/LangChain, FastAPI, SQLAlchemy, React 19, TypeScript, Vite, Docker Compose, Medusa 2.13.6.

## Global Constraints

- Run locally on Windows only; do not use or probe the Mac mini.
- Preserve the live buyer flow and the generic RouteDeck/Medusa ownership boundary.
- Do not add phrase routers, regex intent routing, canned assistant output, mock product data, hidden fallbacks, or automatic commerce retries.
- Keep Medusa Store endpoint templates and HTTP transport inside `medusa/client/`.
- Keep the browser free of direct `/store/*` calls.
- Keep surface affordances and structured agent tools on the same `RouteDeckOperationRunner` path.
- Use focused tests after a coherent slice; do not build a broad new TDD harness.
- Stage only reviewed files under `agent-lab-powered-projects/routedeck`; exclude `artifacts/` and unrelated repository changes.

---

### Task 1: Correct architecture authority and analysis output

**Files:**
- Modify: `context.md`
- Modify: `critical_prompt.md`
- Modify: `docs/framework-architecture.md`
- Modify: `docs/route-deck-reference.md`
- Modify: `docs/medusa-agent-reference-app.md`
- Modify: `architecture/code-map.md`
- Modify: `structure.md`
- Modify: `decisions/ADR-005-operation-centric-state-and-consumer-structure.md`
- Generate locally: `graphify-out/graph.json` (ignored analysis output)

**Produces:** One current authority chain, one identifier policy, and a regenerated code graph that names the compiled API rather than removed pre-refactor files.

- [x] Remove completed items from `context.md`'s known-gap list and describe the current implementation honestly.
- [x] Resolve the real-ID/opaque-handle contradiction: Medusa remains authoritative for real IDs; RouteDeck exposes scoped opaque public handles and resolves them to allowlisted private IDs only at execution.
- [x] Document the clean-break public API and feature-owned binding model introduced below.
- [x] Regenerate Graphify and verify representative current files appear while removed legacy paths do not.

### Task 2: Make the current RouteDeck public API unmistakable

**Files:**
- Modify: `routedeck_core/__init__.py`
- Modify: `routedeck_core/app/__init__.py`
- Modify: `routedeck_core/navigation/__init__.py`
- Modify: canonical contracts and their current consumers to remove compatibility aliases
- Delete: retired manifest/subclass runtime modules after source-consumer proof
- Delete: retired `routedeck_langgraph/{graph,transition,validation}.py` and lazy exports
- Delete: top-level deprecated `react/` compatibility package
- Delete: product re-export wrappers such as `features/cart/handlers.py`
- Modify: `tests/test_public_api.py`
- Modify: `architecture/components/packaging-public-readiness.md`
- Modify: `docs/packaging-roadmap.md`

**Produces:** A small canonical root `__all__` with no legacy aliases, lazy compatibility access, or duplicate public runtime.

- [x] Define the canonical root exports from `app`, `contracts`, `ports`, `projection`, `state`, and `supervision` only.
- [x] Inventory and remove retired manifest, flat model, authoring, projector, subclass-runtime, and topology-parity paths that have no current source consumers.
- [x] Update current call sites to canonical contracts rather than retaining aliases or re-export wrappers.
- [x] Remove the duplicate top-level React package and make `packages/core`, `packages/react`, and `packages/testing` the only JavaScript framework packages.
- [x] Update focused public-API tests and packaging documentation.
- [x] Run `uv run pytest tests/test_public_api.py tests/state/test_public_exports.py -q`.

### Task 3: Give operations typed outcome identity

**Files:**
- Modify: `examples/medusa-agent/backend/medusa_agent/identifiers.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/composition.py`
- Modify: each production operation module under `features/*/operations/`
- Modify: relevant `features/*/feature.py` declarations
- Modify: focused Medusa feature tests that assert outcome values

**Produces:** `MedusaOutcomeType` as the one product-owned vocabulary used by declarations, handlers, and cross-feature transitions.

- [x] Inventory every declared Medusa outcome and define it once as a `StrEnum` member.
- [x] Replace raw outcome literals in production handlers and transitions.
- [x] Keep serialized values stable so existing development data does not drift during the refactor.
- [x] Run focused catalog, cart, checkout, and order operation tests.

### Task 4: Move Medusa bindings into feature-owned modules

**Files:**
- Modify: `routedeck_core/app/bindings.py`
- Create: `examples/medusa-agent/backend/medusa_agent/features/catalog/bindings.py`
- Create: `examples/medusa-agent/backend/medusa_agent/features/cart/bindings.py`
- Create: `examples/medusa-agent/backend/medusa_agent/features/checkout/bindings.py`
- Create: `examples/medusa-agent/backend/medusa_agent/features/orders/bindings.py`
- Modify: feature `__init__.py` files
- Modify: `examples/medusa-agent/backend/medusa_agent/bindings.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/runtime_factory.py`
- Modify: focused binding/contract tests

**Interfaces:**
- `FeatureBindings.merge(*parts: FeatureBindings) -> FeatureBindings` rejects duplicate references.
- Each feature exports a typed `create_*_bindings(...) -> FeatureBindings` factory.
- `bind_medusa_app(...)` composes factories and optional explicit extension bindings, then calls `bind_app(...)` once.

- [x] Add duplicate-safe binding composition to the framework.
- [x] Move constructors and dependency wiring to their owning Medusa features.
- [x] Reduce the root `bindings.py` to dependency composition, not manual catalog repetition.
- [x] Preserve exact startup validation and injected test bindings.
- [x] Run app-binding, framework-import, and representative Medusa flow tests.

### Task 5: Configure model roles explicitly

**Files:**
- Modify: `examples/medusa-agent/backend/medusa_agent/config.py`
- Modify: `examples/medusa-agent/backend/medusa_agent/agent.py`
- Modify: `examples/medusa-agent/infra/compose.yaml`
- Modify: `examples/medusa-agent/README.md`
- Modify: `docs/medusa-agent-reference-app.md`
- Modify: agent configuration tests

**Produces:** Explicit buyer, entry, and turn-policy model settings with no implicit fallback from one role to another.

- [x] Add required `OPENAI_BUYER_MODEL`, `OPENAI_ENTRY_MODEL`, and `OPENAI_TURN_POLICY_MODEL` configuration.
- [x] Keep `OPENAI_API_KEY` common and fail visibly when a live role is not configured.
- [x] Wire each `ChatOpenAI` instance to its declared role.
- [x] Update the local ignored environment for the running demo without printing or committing credentials.
- [x] Run focused live-agent construction and readiness tests.

### Task 6: Split mixed product frontend responsibilities

**Files:**
- Modify: `examples/medusa-agent/frontend/src/app/agentStreamState.ts`
- Create: `examples/medusa-agent/frontend/src/app/agentStreamTransitions.ts`
- Modify: `examples/medusa-agent/frontend/src/app/useAgentStream.ts`
- Split: `examples/medusa-agent/frontend/src/app/app.css` into component-owned CSS files imported by `app.css`
- Modify: focused app-shell tests

**Produces:** A React-independent product chat transition module without a reducer abstraction, plus component-scoped styling, while RouteDeck remains the canonical application-state owner.

- [x] Move pure chat event-to-state transitions out of React setter code.
- [x] Keep request retention, cancellation, SSE parsing, and RouteDeck projection synchronization unchanged.
- [x] Split shell, conversation/composer, surfaces, and navgraph styling without visual redesign.
- [x] Run the focused frontend app-shell suite, typecheck, and production build.

### Task 7: Focused behavior and architecture closeout

**Files:**
- Modify only if evidence exposes a defect.

- [x] Run framework public API, binding, context, supervision, persistence, and boundary checks.
- [x] Run Medusa feature and chat integration checks.
- [x] Run React/core focused tests, typecheck, and builds.
- [x] Verify the real local Medusa readiness endpoints and browser Store-API boundary.
- [x] Exercise greeting, conversational `hello`, browse, product, cart, checkout, review, and confirmation in Chromium.
- [x] Review the complete diff for product leakage, raw SQL, hardcoded phrase routing, fallback paths, secrets, recordings, and unrelated paths.
- [x] Commit the reviewed RouteDeck changes with a path-scoped commit and leave the local stack running for the user.
