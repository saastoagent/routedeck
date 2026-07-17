# RouteDeck Open Source And Medusa Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete RouteDeck as a product-neutral open-source alpha while rebuilding Medusa Agent as the proof that RouteDeck can power a real product agent without absorbing product behavior.

**Architecture:** Work in two locked lanes. The RouteDeck lane finishes framework contracts, React store behavior, generic examples, packaging, and release gates. The Medusa lane first resets the runnable example to app-owned chat only, then reintroduces RouteDeck one layer at a time through product-owned `/api/medusa-agent/*` routes. Medusa is the acceptance fixture, not the framework source of truth.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, FastAPI, Server-Sent Events, LangGraph, `langchain-openai`, React, TypeScript, Vite, Vitest, Node test runner, local/demo Medusa Store API.

---

## Supersession

This plan supersedes `docs/superpowers/plans/2026-06-03-routedeck-medusa-reference-readiness.md` wherever that older plan conflicts with the 2026-06-06 Medusa reset. The older plan remains useful history for contract details, but it is not authority for keeping the runnable Medusa example ahead of Slice 1.

Execution overlay:

- Use `docs/superpowers/plans/2026-06-08-routedeck-medusa-micro-slices.md` for implementation.
- Do not execute this strategic plan as whole milestones or broad tasks.
- If a task would touch both RouteDeck framework code and Medusa runnable example code, split it and execute the framework slice first.
- If a task would introduce more than one visible behavior, split it before editing.

This plan does not supersede:

- `critical_prompt.md`
- `docs/route-deck-reference.md`
- `docs/medusa-agent-reference-app.md`
- `docs/agentic-ui-state-runtime.md`

## Authority Order

Read and obey these files before touching source:

1. `critical_prompt.md`
2. `context.md`
3. `docs/route-deck-reference.md`
4. `docs/medusa-agent-reference-app.md`
5. `docs/agentic-ui-state-runtime.md`
6. `work_prompt.md`
7. `architecture/code-map.md`
8. `test_index/README.md`

If implementation conflicts with the reference, change the implementation. Do not weaken the reference to excuse drift.

## Product And Framework Boundary

RouteDeck owns:

- product-neutral Python models and validation
- manifest, snapshot, projection, navgraph, capability, operation, dispatch, surface, affordance, event, diagnostics, introspection, and client-store contracts
- optional LangGraph adapter helpers
- React store, hooks, type exports, and debugger surfaces
- generic framework API shapes and examples
- open-source package metadata and docs

Medusa owns:

- the commerce assistant, prompts, LLM calls, and LangGraph agent graph
- product planning context construction
- product-owned HTTP routes under `/api/medusa-agent/*`
- local/demo Medusa Store API calls and fixture reset
- cart, checkout, admin, payment, shipping, and fulfillment policy when later slices explicitly allow them
- product UI copy, visible product labels, public entity keys, and shopper-facing messages
- all product side effects

## Non-Negotiable Gates

- Medusa Slice 1 ships first and contains no RouteDeck runtime, projection, manifest, dispatch, navgraph, product surface, diagnostics, Store API calls, cart writes, or `/api/routedeck/*`.
- No deterministic phrase router, alias router, command menu, hardcoded catalog, or fake all-slices demo is accepted as the agent.
- RouteDeck framework source must stay product-neutral. `routedeck_core`, `routedeck_langgraph`, and `react/src` must not contain Medusa, SaaStoAgent, Corpus, cart, checkout, payment, shipping, or admin domain behavior.
- Product-specific APIs stay product-owned. Medusa RouteDeck-derived state uses `/api/medusa-agent/*`, never `/api/routedeck/medusa/*`.
- Browser location is product path state. Optional surface or presentation replay state goes in query params such as `surface_id`.
- Visual navgraph selection is read-only inspector focus. It must not dispatch, navigate, mutate graph state, or change browser URL.
- Product surfaces live in the chat/workbench stream for agent-centric Medusa. They are not navgraph controls and not detached debugger panels.
- Product action chips attach to chat/workbench. They do not come from clickable navgraph nodes and do not render `legal_operations` wholesale.
- Every semantic surface affordance must also be represented in product-agent planning context.
- Once a product projection or surface is visible, chat requests that claim to
  browse, open, select, compare, or otherwise change that surface must update the
  same browser-visible projection through the same Medusa-owned runtime boundary
  as the equivalent surface affordance. Assistant prose alone is not completion.
- Public chat must answer product names, prices, variants, colors, sizes,
  availability, cart contents, and current surface state only from projection,
  planning context, or a product tool result. Model-only catalog facts are drift.
- Read-only Medusa slices may still perform guarded read transitions, surface
  changes, projection refreshes, and canonical path updates. Read-only forbids
  product side effects, not runtime-accepted projection movement.
- `conversation_id`, LangGraph `thread_id`, projection/session state, action
  dispatch, route-stream events, debug/inspect context, and projection version
  must refer to the same product session before a visible slice is called ready.
- Dynamic chips must derive from current projection/planning context or an agent
  proposal, refresh after projection changes, avoid current-node no-ops unless
  intentionally labelled as refresh/reload, and remain chat-doable.
- Product-agent SSE, RouteDeck state SSE, and diagnostics streams remain separate.
- Diagnostics remain read-only and out of public chat.
- `RouteDeckStore` mirrors runtime state only. It does not become graph truth.

## File Structure

RouteDeck framework files:

- Modify `routedeck_core/models.py`: keep schema inventory aligned with `docs/route-deck-reference.md`.
- Modify `routedeck_core/runtime.py`: harden projection/navgraph/default-state builders and event helpers.
- Modify `routedeck_core/validation.py`: validate capability, action, node, edge, surface, entity, and hidden-operation consistency.
- Modify `routedeck_core/__init__.py`: export only product-neutral public models and helpers.
- Modify `routedeck_langgraph/*.py`: keep optional adapter behavior product-neutral.
- Modify `tests/*.py`: lock reference-compatible Python behavior.

React package files:

- Modify `react/src/types.ts`: keep TypeScript contract parity with Python models.
- Modify `react/src/RouteDeckStore.ts`: preserve stream handling, dispatch state, hidden route operation behavior, and runtime-state mirroring.
- Modify `react/src/RouteDeckProvider.tsx`: expose product-neutral hooks for projection, operations, capabilities, entities, affordances, diagnostics, status, navigation, and dispatch.
- Modify `react/src/index.ts`: export public React APIs.
- Modify `react/package.json`: remove `private: true` only when package build, declaration, tests, docs, and notices are ready.
- Modify `react/tests/*.mjs` and `react/tests/*.tsx`: protect store and public type behavior.

Medusa reset files:

- Keep `examples/medusa-agent/backend/main.py`, `app.py`, `core/config.py`, `core/protocol.py`, `routes/chat.py`, `services/chat_service.py`, `services/graph_builder.py`, and `tests/test_slice1_chat.py`.
- Keep `examples/medusa-agent/frontend/src/App.tsx`, `src/hooks/useSSEChat.ts`, `src/main.tsx`, `src/styles.css`, and `src/App.test.tsx`.
- Delete or quarantine later-slice runnable files until their slice is reintroduced: `backend/routes/routedeck.py`, `backend/services/routedeck_runtime.py`, `backend/services/routedeck_manifest.py`, `backend/services/routedeck_prompt.py`, `backend/services/routedeck_provider.py`, `backend/services/planning_context.py`, `backend/services/agent_tools.py`, `backend/services/medusa_store.py`, `backend/services/medusa_setup.py`, `backend/services/commerce_state.py`, `backend/services/commerce_refs.py`, `frontend/src/hooks/useRouteDeckProjection.ts`, and `frontend/src/hooks/useRouteDeckStatus.ts`.
- Delete or rewrite later-slice tests that keep RouteDeck behavior alive before Slice 2.

Medusa RouteDeck reintroduction files:

- Recreate product-owned RouteDeck integration under `examples/medusa-agent/backend/services/` only after Slice 1 passes.
- Recreate product-owned routes under `/api/medusa-agent/*`, not `/api/routedeck/*`.
- Recreate frontend RouteDeck consumption only after the React package is ready to be consumed as a package, not copied through product-local types.

Open-source docs and metadata:

- Modify `README.md`.
- Modify `docs/packaging-roadmap.md`.
- Modify `docs/using-routedeck.md`.
- Modify `docs/minimal-example.md`.
- Modify `architecture/components/packaging-public-readiness.md`.
- Modify `architecture/components/core-runtime-contract.md`.
- Modify `architecture/components/react-runtime-debugger.md`.
- Modify `architecture/components/examples-and-adoption.md`.
- Modify `test_index/README.md`.
- Modify `THIRD_PARTY_NOTICES.md` if dependencies or public package contents change.

## Milestones

| Milestone | RouteDeck state | Medusa state | Exit proof |
| --- | --- | --- | --- |
| M0 Baseline | Authority docs and dirty worktree understood. | Current messy example identified as reset target. | Status, focused tests, and drift scan captured. |
| M1 Reset | Framework untouched except guard docs. | Runnable Medusa is Slice 1 chat only. | Slice 1 backend/frontend tests pass and no RouteDeck endpoints exist. |
| M2 Framework Alpha | Core, LangGraph adapter, React store, docs, examples, and packaging pass release gates. | Medusa still chat-only. | Root pytest, React tests, package checks, doc coverage, and no product leaks. |
| M3 Projection Proof | RouteDeck projection/state API contract is stable. | Medusa exposes product-owned projection/state without dispatch. | `/api/medusa-agent/projection` works and public UI still stays chat-first; this is static orientation/projection proof, not a usable product-surface slice unless chat convergence is also proven. |
| M4 Surface Proof | Surface, affordance, entity, dispatch, stream, and store contracts are stable. | Medusa UI emits surface events and chat uses matching planning context. | UI click and chat request converge on one runtime boundary, browser projection updates, URL path state agrees, and product facts are grounded. |
| M5 Commerce Proof | RouteDeck stays product-neutral. | Medusa reads and writes only local/demo fixture data with reset. | Browse/detail/cart proof with no private ID leaks. |
| M6 Public Alpha | Packages and docs are ready for open-source alpha. | Medusa proves adoption from packages. | Clean install smoke, docs, screenshots, tests, and release checklist pass. |

## Task 0: Baseline And Worktree Protection

**Files:**

- Read: `critical_prompt.md`
- Read: `context.md`
- Read: `docs/route-deck-reference.md`
- Read: `docs/medusa-agent-reference-app.md`
- Read: `docs/agentic-ui-state-runtime.md`
- Read: `architecture/code-map.md`
- Read: `test_index/README.md`

- [ ] **Step 1: Inspect status**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core"
git status --short --branch
```

Expected: unrelated dirty files are named and preserved. Do not overwrite or revert unrelated user work.

- [ ] **Step 2: Run current RouteDeck reference guard**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
python -m pytest tests/test_medusa_reference_slice0.py -q
```

Expected: the reference guard passes before implementation begins. If it fails, fix the guard or docs drift before touching Medusa source.

- [ ] **Step 3: Capture current Medusa drift**

Run:

```powershell
rg -n "routes/routedeck|RouteDeck|route-stream|projection|dispatch|navgraph|Store API|cart|checkout|diagnostic|phrase_router|alias_router|command_router" examples/medusa-agent
```

Expected: this command currently shows later-slice drift. Use it as the deletion/rewriting inventory for Task 1.

## Task 1: Reset Medusa To Barebones App-Owned Chat

**Files:**

- Modify `examples/medusa-agent/README.md`
- Modify `examples/medusa-agent/backend/main.py`
- Modify `examples/medusa-agent/backend/routes/chat.py`
- Modify `examples/medusa-agent/backend/services/chat_service.py`
- Modify `examples/medusa-agent/backend/services/graph_builder.py`
- Modify `examples/medusa-agent/backend/tests/test_slice1_chat.py`
- Modify `examples/medusa-agent/frontend/src/App.tsx`
- Modify `examples/medusa-agent/frontend/src/hooks/useSSEChat.ts`
- Modify `examples/medusa-agent/frontend/src/App.test.tsx`
- Delete or quarantine later-slice files listed in the Medusa reset file structure section.

- [ ] **Step 1: Write backend reset tests**

Add or update tests so they prove:

- `POST /api/medusa-agent/agent/stream` returns `text/event-stream`.
- `conversation_id` maps to `configurable.thread_id`.
- `message_delta` frames stream from live or mocked LangGraph execution.
- missing `OPENAI_API_KEY` emits an SSE `error` with code `openai_api_key_missing`.
- no `/api/medusa-agent/projection`, `/api/medusa-agent/action`, `/api/medusa-agent/inspect`, `/api/medusa-agent/route-stream`, or `/api/routedeck/*` route is registered.
- no RouteDeck module is imported in Slice 1 backend source.

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice1_chat.py -q
```

Expected before implementation: tests fail if later-slice routes still exist.

- [ ] **Step 2: Write frontend reset tests**

Add or update tests so they prove:

- first screen is the chat experience
- composer sends one message to `/api/medusa-agent/agent/stream`
- streamed `message_delta` text appends incrementally
- no RouteDeck, navgraph, route inspector, diagnostics, cart, product panel, checkout, or Store API UI appears
- the app handles SSE `error` visibly without fake assistant text

Run:

```powershell
cd examples/medusa-agent/frontend
npm test
```

Expected before implementation: tests fail if RouteDeck UI remains mounted.

- [ ] **Step 3: Strip later-slice backend**

Remove route registration and imports for RouteDeck, Store API, cart, setup, diagnostics, and action dispatch. Keep only:

- FastAPI app
- health endpoint if tests require it
- chat SSE route
- config
- SSE protocol helpers
- minimal LangGraph builder
- chat stream service

The Slice 1 backend must not import from `routedeck_core`, `routedeck_langgraph`, Medusa SDK/API clients, or later-slice local services.

- [ ] **Step 4: Strip later-slice frontend**

Render only:

- app header in Medusa language
- message list
- composer
- stream/error state

Do not render navgraph, inspector, RouteDeck action chips, product cards, cart summaries, checkout, diagnostics, or operation/debug text.

- [ ] **Step 5: Run reset validation**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
python -m pytest examples/medusa-agent/backend/tests/test_slice1_chat.py -q
cd examples/medusa-agent/frontend
npm test
cd ..\..\..
python -m pytest tests/test_medusa_reference_slice0.py -q
```

Expected: all pass, proving Medusa starts as a normal product-owned chat agent.

## Task 2: Lock RouteDeck Core Contracts For Open Source

**Files:**

- Modify `routedeck_core/models.py`
- Modify `routedeck_core/runtime.py`
- Modify `routedeck_core/validation.py`
- Modify `routedeck_core/__init__.py`
- Modify `tests/test_core_contract.py`
- Modify `tests/test_projection_contract.py`
- Modify `tests/test_runtime_store_contract.py`

- [ ] **Step 1: Add schema inventory parity tests**

Tests must cover:

- `RouteDeckManifest.capabilities`
- `RouteDeckProjection.capabilities`
- `RouteDeckProjection.navgraph`
- `RouteDeckProjection.available_entities`
- `RouteDeckProjection.surface_affordances`
- `RouteDeckDispatchInput.surface_event`
- `RouteDeckSemanticObservation`
- alias serialization for `RouteDeckBindingExpression.from`
- alias serialization for navgraph edge `from` and `to`

Run:

```powershell
python -m pytest tests/test_core_contract.py tests/test_projection_contract.py tests/test_runtime_store_contract.py -q
```

Expected: tests pass only when Python models match `docs/route-deck-reference.md`.

- [ ] **Step 2: Harden runtime helpers**

`build_projection(...)` must:

- default capabilities from manifest when not supplied
- default empty entity and affordance pools
- derive a navgraph from manifest nodes and edges
- keep blocked operations out of public `legal_operations`
- preserve projection version and diagnostics
- never synthesize product-specific operations

- [ ] **Step 3: Harden validation**

`validate_manifest(...)` must reject:

- unknown action ids in edges or nodes
- unknown capability ids on actions, nodes, or edges
- unknown allowed-node patterns
- sensitive fields not covered by masking policy when a policy is supplied
- action ids that start with `route.` when they are configured as product-facing chips in docs or examples

- [ ] **Step 4: Run core validation**

Run:

```powershell
python -m pytest tests/test_core_contract.py tests/test_projection_contract.py tests/test_runtime_store_contract.py -q
python -m pytest tests/test_medusa_reference_slice0.py -q
```

Expected: core contract and drift guard pass.

## Task 3: Harden React Store And Public API

**Files:**

- Modify `react/src/types.ts`
- Modify `react/src/RouteDeckStore.ts`
- Modify `react/src/RouteDeckProvider.tsx`
- Modify `react/src/index.ts`
- Modify `react/tests/*.mjs`
- Modify `react/tests/*.tsx`

- [ ] **Step 1: Add TypeScript parity tests**

Tests must cover:

- projection normalization preserves capabilities, navgraph, available entities, and surface affordances
- `receiveEvent(...)` applies `projection_update` and `operation_completed` only from RouteDeck state events
- `connectStream()` subscribes only to RouteDeck event types
- local `route.*` helpers remain internal store operations and are not chip-rendering inputs
- hooks expose capabilities, entities, affordances, diagnostics, navigation, status, and dispatch without mutating state

Run:

```powershell
cd react
npm test
```

Expected: tests pass and TypeScript-facing exports remain product-neutral.

- [ ] **Step 2: Harden store invariants**

`RouteDeckStore` must:

- mirror runtime state
- normalize missing optional fields to empty arrays or objects
- keep dispatch pending state visible
- apply stream events only when they carry valid state or projection payloads
- avoid generating product operations or product side effects locally

- [ ] **Step 3: Harden exports**

`react/src/index.ts` must export every public type and hook needed by a product without exporting Medusa or SaaStoAgent-specific names.

- [ ] **Step 4: Run React validation**

Run:

```powershell
cd react
npm test
rg -n "Medusa|medusa|SaaStoAgent|Corpus|cart|checkout|product_ref|variant_ref" src tests package.json
```

Expected: tests pass and the search returns no framework package product leaks.

## Task 4: Finish Open-Source Package Readiness

**Files:**

- Modify `pyproject.toml`
- Modify `react/package.json`
- Modify `README.md`
- Modify `docs/packaging-roadmap.md`
- Modify `docs/using-routedeck.md`
- Modify `docs/minimal-example.md`
- Modify `architecture/components/packaging-public-readiness.md`
- Modify `THIRD_PARTY_NOTICES.md`
- Modify `.gitignore` if generated packaging artifacts need exclusion.

- [ ] **Step 1: Python package smoke**

Run:

```powershell
python -m pip install -e .
python - <<'PY'
from routedeck_core import RouteDeckManifest, RouteDeckProjection
print(RouteDeckManifest.__name__, RouteDeckProjection.__name__)
PY
```

Expected: package imports work from an editable install.

- [ ] **Step 2: React package smoke**

Prepare the package for open-source alpha:

- keep `react` and `react-dom` as peer dependencies
- keep `@xyflow/react` as a peer dependency if debugger export still uses it
- add declaration/build policy before removing `private: true`
- document source-export support if declaration build is intentionally deferred

Run:

```powershell
cd react
npm test
npm pack --dry-run
```

Expected: dry run lists only intended package files.

- [ ] **Step 3: Public docs scrub**

Docs must explain:

- RouteDeck is a framework, not a product shell
- product APIs remain product-owned
- RouteDeck can be used without Medusa, Corpus, or SaaStoAgent
- Medusa is a reference example
- diagnostics are read-only
- route/state streams are separate from agent text streams

Run:

```powershell
rg -n "RouteDeck owns Medusa|RouteDeck hosts Medusa|/api/routedeck/(medusa|cart|checkout|payment|shipping|admin)|fake all-slices|deterministic command" README.md docs architecture
```

Expected: no hits that imply product/framework ownership leakage.

- [ ] **Step 4: Public readiness validation**

Run:

```powershell
python -m pytest tests -q
cd react
npm test
cd ..
python scripts/check_doc_coverage.py
```

Expected: all tests pass; doc coverage warnings are either fixed or recorded with rationale.

## Task 5: Reintroduce Medusa Slice 2 Projection Only

**Files:**

- Create or modify `examples/medusa-agent/backend/services/routedeck_provider.py`
- Create or modify `examples/medusa-agent/backend/services/routedeck_manifest.py`
- Create or modify `examples/medusa-agent/backend/services/routedeck_runtime.py`
- Create or modify `examples/medusa-agent/backend/routes/routedeck.py`
- Modify `examples/medusa-agent/backend/main.py`
- Modify `examples/medusa-agent/backend/tests/test_slice2_routedeck.py`
- Modify `examples/medusa-agent/frontend/src/App.tsx` only if showing read-only status is explicitly in scope.

- [ ] **Step 1: Add product-owned projection endpoint tests**

Tests must prove:

- `GET /api/medusa-agent/projection` exists
- `/api/routedeck/*` does not exist in the Medusa example
- projection contains current context, graph node, navigation, surfaces, legal operations, capabilities, navgraph, entities, affordances, and diagnostics fields as allowed by Slice 2
- Slice 2 does not dispatch operations or perform cart writes
- public response contains no private Medusa ids

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice2_routedeck.py -q
```

Expected before implementation: fails because Slice 2 routes were removed in Task 1.

- [ ] **Step 2: Implement projection wrapper**

The Medusa route must call product runtime code and return RouteDeck-derived projection under Medusa language:

- route path: `/api/medusa-agent/projection`
- no generic `/api/routedeck/*`
- no dispatch
- no inspect
- no route stream
- no cart write

- [ ] **Step 3: Run Slice 1 plus Slice 2 backend tests**

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice1_chat.py tests/test_slice2_routedeck.py -q
```

Expected: Slice 1 chat remains clean while Slice 2 projection exists.

## Task 6: Add Read-Only Navgraph, Deeplinks, And Inspector

**Files:**

- Modify `examples/medusa-agent/backend/services/routedeck_manifest.py`
- Modify `examples/medusa-agent/backend/services/routedeck_runtime.py`
- Modify `examples/medusa-agent/frontend/src/App.tsx`
- Modify `examples/medusa-agent/frontend/src/styles.css`
- Modify `examples/medusa-agent/frontend/src/App.test.tsx`

- [ ] **Step 1: Add navgraph tests**

Frontend and backend tests must prove:

- navgraph renders graph nodes and route edges
- selecting a graph node updates only local inspector focus
- graph selection does not dispatch
- graph selection does not change browser URL
- product path deeplinks use `/`, `/browse`, `/detail/:handle`, and `/cart`
- `surface_id` query state is only presentation/surface replay state
- no `?rd_node=...` canonical URL is shown

Run:

```powershell
cd examples/medusa-agent/frontend
npm test
```

Expected: tests fail until UI and URL codec are implemented.

- [ ] **Step 2: Implement product URL codec**

The frontend must encode and decode:

- `/` -> home
- `/browse` -> browse
- `/detail/t-shirt` -> detail with public product handle
- `/cart` -> cart
- `?surface_id=detail.product_detail` -> active surface replay only

- [ ] **Step 3: Run navgraph validation**

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice2_routedeck.py -q
cd ..\frontend
npm test
```

Expected: navgraph and deeplink tests pass without operation dispatch.

## Task 7: Add First Surface Affordance Dispatch

**Files:**

- Modify `examples/medusa-agent/backend/services/routedeck_runtime.py`
- Modify `examples/medusa-agent/backend/routes/routedeck.py`
- Modify `examples/medusa-agent/backend/tests/test_slice3_routedeck_runtime.py`
- Modify `examples/medusa-agent/frontend/src/hooks/useRouteDeckProjection.ts`
- Modify `examples/medusa-agent/frontend/src/App.tsx`
- Modify `examples/medusa-agent/frontend/src/App.test.tsx`

- [ ] **Step 1: Add surface-event tests**

Tests must prove:

- one read-only product card or browse/detail click emits `surface_event`
- runtime resolves affordance, entity binding, required args, readiness, auth, and policy
- unknown affordance, stale entity, unauthorized entity, and missing args reject or clarify
- UI never sends private product, variant, cart, or line ids
- variant selection and add-to-cart are intentionally out of scope here; they
  belong to the later variant and first-write micro-slices.

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice3_routedeck_runtime.py -q
cd ..\frontend
npm test
```

Expected before implementation: fails where surface events are missing.

- [ ] **Step 2: Implement surface-event dispatch**

The runtime must resolve:

```text
surface_event
  -> declared RouteDeckSurfaceAffordance
  -> RouteDeckAvailableEntity
  -> RouteDeckDispatchInput
  -> operation readiness and args
  -> product runtime commit/reject/review
  -> RouteDeckDispatchResult
```

- [ ] **Step 3: Run dispatch validation**

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice3_routedeck_runtime.py -q
cd ..\frontend
npm test
```

Expected: surface dispatch passes and navgraph remains read-only.

## Task 8: Add Product-Agent Planning Context And Chat Tooling

**Files:**

- Create or modify `examples/medusa-agent/backend/services/planning_context.py`
- Modify `examples/medusa-agent/backend/services/routedeck_prompt.py`
- Modify `examples/medusa-agent/backend/services/agent_tools.py`
- Modify `examples/medusa-agent/backend/services/chat_service.py`
- Modify `examples/medusa-agent/backend/services/graph_builder.py`
- Modify `examples/medusa-agent/backend/tests/test_slice3_agent_tools.py`
- Modify `examples/medusa-agent/backend/tests/test_slice1_chat.py`
- Modify `examples/medusa-agent/frontend/src/App.tsx`
- Modify `examples/medusa-agent/frontend/src/hooks/useSSEChat.ts`
- Modify `examples/medusa-agent/frontend/src/hooks/useRouteDeckProjection.ts`
- Modify `examples/medusa-agent/frontend/src/App.test.tsx`

- [ ] **Step 1: Add planning-context tests**

Tests must prove planning context includes:

- current node and surface
- active surface summary
- valid surface options
- legal product operations
- available and rendered entities
- surface affordances
- readiness and missing-arg metadata
- prompt-ready rendered product facts when the assistant is allowed to answer
  catalog/detail/cart questions

Tests must prove planning context excludes:

- hidden `route.*`
- blocked operations
- private Medusa ids
- raw graph state
- diagnostics
- endpoint paths
- unbound dispatch payloads

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice3_agent_tools.py tests/test_slice1_chat.py -q
```

Expected before implementation: fails where planning context is missing or stale.

- [ ] **Step 2: Implement planning context builder**

`build_medusa_planning_context(...)` is product-owned and must stay outside `routedeck_core`. It reads `RouteDeckProjection` and returns Medusa-safe planning data for the product agent.

- [ ] **Step 3: Implement chat operation resolution**

Agent tools must:

- select product operation ids from planning context
- bind only visible or available `entity_key`s
- request clarification for ambiguous entities
- dispatch through the same runtime boundary as UI surface events
- stream product-safe semantic observations
- update the browser-visible projection through RouteDeck state event or
  explicit projection refresh outside assistant prose
- update canonical path state or projected deeplink path for read navigation,
  such as `/browse` after "show products"
- leave debug context showing the route context, planning context, accepted
  operation or `surface_intent`, public entity binding, and latest projection
  version
- never call Store API directly from the LLM tool layer
- never answer product facts that are absent from projection, planning context,
  or product tool output

- [ ] **Step 4: Run chat and tool validation**

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice1_chat.py tests/test_slice3_agent_tools.py tests/test_slice3_routedeck_runtime.py -q
```

Expected: chat and surface dispatch converge on one runtime boundary, browser
projection updates, product facts are grounded, and assistant SSE remains
separate from projection/runtime state.

## Task 9: Add Local/Demo Medusa Store API Commerce Proof

**Files:**

- Modify `examples/medusa-agent/backend/services/medusa_store.py`
- Modify `examples/medusa-agent/backend/services/medusa_setup.py`
- Modify `examples/medusa-agent/backend/services/commerce_state.py`
- Modify `examples/medusa-agent/backend/services/commerce_refs.py`
- Modify `examples/medusa-agent/backend/services/routedeck_runtime.py`
- Modify `examples/medusa-agent/backend/tests/test_slice3_routedeck_runtime.py`
- Modify `examples/medusa-agent/README.md`

- [ ] **Step 1: Add fixture-bound commerce tests**

Tests must prove:

- products come from local/demo Store API or test doubles
- unavailable Store API blocks commerce operations without fake products
- public product handles and entity keys are used in UI and chat
- private product, variant, cart, and line ids stay inside runtime refs
- cart writes happen only after explicit UI or chat intent
- writes are scoped to a resettable local/demo fixture

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice3_routedeck_runtime.py -q
```

Expected: tests pass with mocked Store API and can be smoke-tested against local/demo Medusa.

- [ ] **Step 2: Implement Store API adapter**

Adapter rules:

- no production Medusa dependency
- no external payment provider in this task
- no admin mutation in this task
- no checkout in this task
- all private ids mapped to opaque refs before projection, planning context, UI, or chat

- [ ] **Step 3: Run commerce validation**

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests -q
```

Expected: backend tests pass with Store API mocked; manual local/demo Store API smoke is recorded separately.

## Task 10: Add RouteDeck State Stream And Diagnostics After Product Behavior Is Stable

**Files:**

- Modify `examples/medusa-agent/backend/routes/routedeck.py`
- Modify `examples/medusa-agent/backend/services/routedeck_runtime.py`
- Modify `examples/medusa-agent/frontend/src/App.tsx`
- Modify `examples/medusa-agent/frontend/src/App.test.tsx`
- Modify `docs/medusa-agent-reference-app.md`

- [ ] **Step 1: Add stream separation tests**

Tests must prove:

- product-agent chat stream uses `message_delta`
- RouteDeck state stream uses `projection_update`, `operation_started`, `operation_completed`, `guard_failure`, `surface_update`, or `runtime_status`
- diagnostics stream or inspect route returns read-only introspection
- diagnostics do not become public chat
- state stream does not emit assistant prose as semantic text

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests -q
cd ..\frontend
npm test
```

Expected: tests pass and streams are separate.

- [ ] **Step 2: Implement read-only diagnostics**

Diagnostics can show:

- current node
- reachable nodes
- legal and blocked operations
- guard explanations
- active surface
- surface projection state
- navgraph topology
- route traces
- projection version
- recent runtime events

Diagnostics must not:

- dispatch operations from a graph click
- replace product chat
- expose private ids in public chat
- become product action chip source
- teach product agents hidden `route.*` operations

## Task 11: Minimal Generic Examples For Open Source

2026-06-09 recalibration: Task 11 is deferred unless the user explicitly asks
for separate product-neutral RouteDeck examples. Do not execute this task to
satisfy a Medusa Agent visible slice. The current visible implementation lane is
`examples/medusa-agent/`; a prior attempt to create `examples/minimal-*` demos
was deleted because it drifted away from the Medusa Agent vision.

**Files:**

- Create `examples/minimal-langgraph-adapter/README.md`
- Create `examples/minimal-langgraph-adapter/minimal_graph.py`
- Create `examples/minimal-langgraph-adapter/test_minimal_graph.py`
- Create `examples/minimal-fastapi-react/README.md`
- Create `examples/minimal-fastapi-react/backend/main.py`
- Create `examples/minimal-fastapi-react/backend/tests/test_app.py`
- Create `examples/minimal-fastapi-react/frontend/package.json`
- Create `examples/minimal-fastapi-react/frontend/src/App.tsx`
- Create `examples/minimal-fastapi-react/frontend/src/App.test.tsx`
- Modify `docs/minimal-example.md`
- Modify `README.md`
- Modify `tests/test_langgraph_adapter.py`
- Modify `react/tests/*.mjs`

- [ ] **Step 1: Create minimal example skeletons**

Create the listed files with product-neutral language only. Use names such as
`home`, `review`, `complete`, `approve.draft`, and `open.review` instead of
Medusa, cart, checkout, SaaStoAgent, or Corpus domain names. The backend example
must expose projection, dispatch, inspect, and state stream behavior without
product-specific APIs. The frontend example must consume `@routedeck/react`
instead of copying local RouteDeck types.

- [ ] **Step 2: Verify examples are product-neutral**

Run:

```powershell
rg -n "Medusa|SaaStoAgent|Corpus|cart|checkout|payment|shipping|admin" examples/minimal-langgraph-adapter examples/minimal-fastapi-react docs/minimal-example.md
```

Expected: no product-specific hits.

- [ ] **Step 3: Add clean-install smoke docs**

Docs must provide commands for:

- install Python package editable
- install React package or link local package
- run minimal backend
- run minimal frontend
- see projection
- dispatch one product-neutral operation
- inspect read-only navgraph/diagnostics

- [ ] **Step 4: Run minimal example validation**

Run the exact commands documented in `docs/minimal-example.md`. If the examples cannot run yet, fix the examples or remove unsupported claims.

## Task 12: Final Open-Source And Medusa Acceptance

**Files:**

- Modify `context.md`
- Create `logs/<date>-routedeck-open-source-medusa-closeout.md`
- Create `context_checkpoints/<date>-routedeck-open-source-medusa.md`
- Modify `test_index/README.md`
- Modify `architecture/code-map.md` only if source ownership moved.

- [ ] **Step 1: Run full RouteDeck verification**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
python -m pytest tests -q
cd react
npm test
cd ..
python scripts/check_doc_coverage.py
```

Expected: all pass or advisory warnings are documented with exact rationale.

- [ ] **Step 2: Run Medusa verification**

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests -q
cd ..\frontend
npm test
```

Expected: all pass.

- [ ] **Step 3: Run drift scans**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
rg -n "api/routedeck/(medusa|propertydesk|corpus|saastoagent|cart|checkout|order|payment|shipping|fulfillment|admin)|phrase_router|alias_router|command_router|intent_map" .
rg -n "Medusa|medusa|cart|checkout|payment|shipping|admin|product_ref|variant_ref" routedeck_core routedeck_langgraph react/src examples/minimal-langgraph-adapter examples/minimal-fastapi-react
```

Expected: no framework or generic-example product leaks. Medusa-specific hits are allowed only inside `docs/medusa-agent-reference-app.md` and `examples/medusa-agent`.

- [ ] **Step 4: Manual browser smoke**

With local/demo Medusa unavailable:

- chat works or reports missing configuration honestly
- projection blocks commerce actions
- no fake products appear
- no RouteDeck internals appear in public chat

With local/demo Medusa available:

- `/` opens Medusa chat-first home
- `/browse` shows product surface after RouteDeck slice enables surfaces
- `/detail/<public-handle>?surface_id=detail.product_detail` restores product detail
- `/cart` restores cart summary
- navgraph selection changes inspector only
- product card click emits surface event
- chat request binds the same entity and dispatch boundary as the click
- from `/`, "show products" changes the visible projection to browse through
  runtime state or explicit projection refresh, not assistant prose alone
- product detail/chat answers use only product facts present in projection,
  planning context, or product tool output
- debug view shows the full context thread, route context, accepted operation or
  surface intent, and latest projection version while the slice is under
  development
- private ids do not appear in public UI or chat

- [ ] **Step 5: Closeout**

Follow `work_prompt.md`:

- create log entry
- create checkpoint
- archive `context.md` if materially changed
- rewrite `context.md` as concise restart snapshot
- name changed files by `architecture/code-map.md` subsystem row
- update docs/test index/architecture anchors
- run doc coverage
- run fastest meaningful validation command for changed areas

## Commit Sequence

Use small commits in this order:

1. `docs: tighten RouteDeck vision stream and store guardrails`
2. `test: lock Medusa Slice 1 reset boundaries`
3. `refactor: reset Medusa example to chat-only Slice 1`
4. `test: lock RouteDeck core open-source contracts`
5. `feat: harden RouteDeck core projection and validation`
6. `test: lock React store and stream invariants`
7. `feat: harden RouteDeck React package API`
8. `docs: update RouteDeck open-source packaging readiness`
9. `feat: add Medusa product-owned RouteDeck projection`
10. `feat: add Medusa read-only navgraph and deeplinks`
11. `feat: add Medusa surface affordance dispatch`
12. `feat: add Medusa planning context chat dispatch`
13. `feat: add local demo Medusa commerce proof`
14. `feat: add read-only diagnostics and route stream`
15. `docs: close out RouteDeck open-source Medusa proof`

Do not combine reset, framework package hardening, and Medusa later-slice behavior in one commit.

## Self-Review

Spec coverage:

- The critical RouteDeck vision is protected by `critical_prompt.md`, `docs/route-deck-reference.md`, and Tasks 2 through 4.
- The Medusa reset is protected by Task 1 before any RouteDeck reintroduction.
- RouteDeck open-source readiness is protected by Tasks 2 through 4 and Task 11.
- Medusa powered by RouteDeck is protected by Tasks 5 through 10.
- Final acceptance and closeout are protected by Task 12.

Boundary coverage:

- Product graph truth remains product-owned.
- Product APIs remain product-owned.
- RouteDeck remains product-neutral.
- Medusa consumes RouteDeck contracts instead of redefining them.
- Chat, surfaces, automation, and diagnostics share capability facts but stay in separate channels.
- Surface actions and chat operations converge only through validated dispatch.

Known execution risk:

- The current runnable Medusa tree contains later-slice behavior. Execute Task 1 before trusting any later Medusa tests.
- The current RouteDeck code already contains some reference-aligned models and React hooks. Execute Tasks 2 and 3 as lock-and-harden work, not blind greenfield implementation.
- The npm package is still marked private. Remove that only after package dry-run, declarations/build policy, docs, and notices are ready.
