# RouteDeck Medusa Micro-Slice Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the RouteDeck open-source and Medusa Agent rebuild plan through small, testable slices that cannot hide UI drift, fake agent behavior, or framework/product leakage.

**Architecture:** This plan is the execution overlay for `docs/superpowers/plans/2026-06-08-routedeck-open-source-medusa-agent.md`. Each micro-slice changes exactly one behavior boundary, proves it with a focused test or scan, and stops if the previous slice is not green. RouteDeck framework work and Medusa product-example work stay separated until package-level RouteDeck contracts are stable.

**Tech Stack:** Python 3.11, pytest, FastAPI, Server-Sent Events, LangGraph, React, TypeScript, Vite, Vitest, Node test runner, Pydantic v2, RouteDeck Python and React packages.

---

## Why This Exists

The earlier larger slices failed because they allowed three regressions to hide inside one implementation pass:

- extra UI arrived before the proof needed it
- deterministic command behavior was presented as the agent
- Medusa product behavior and RouteDeck framework semantics leaked into each other

This plan prevents that by changing the execution unit:

```text
one micro-slice = one visible behavior + one boundary + one test file + one rollback point
```

Do not execute the strategic plan by whole tasks. Execute the micro-slices below.

## Behavior Contract Rules

A micro-slice is not complete because files changed or tests were added. A micro-slice is complete only when its expected runtime behavior is true.

Use this rule when executing every slice:

- First read the behavior contract for the slice.
- Then read the file list and task steps.
- If the file list or task wording conflicts with the behavior contract, stop and fix the plan before coding.
- If a slice would create behavior that belongs to a later slice, split it or reject the work.
- If behavior cannot be proven with one focused test file or one focused scan, split the slice.

Each behavior contract has four parts:

- Expected behavior: what the user, package consumer, agent, or runtime observes.
- Public contract: the endpoint, stream, URL, schema, package API, or UI surface that carries the behavior.
- Forbidden behavior: what must not exist yet.
- Green evidence: the proof required before the slice can be called done.

## Global Convergence And Grounding Gate

This gate exists because a projected surface can look convincing while chat and
RouteDeck state are still disconnected. No future Medusa slice may be described
as "usable", "ready for testing", or "first usable slice" unless this gate is
green for the behavior that slice exposes.

Required for any visible product-surface slice:

- Chat-to-projection convergence: a normal chat request that claims to browse,
  open, select, compare, or otherwise change the visible product surface must
  drive the same Medusa-owned RouteDeck runtime boundary as the matching surface
  affordance. The browser-visible projection must change, or the assistant must
  explicitly say the action is unavailable in the current slice.
- Grounded product facts: public chat may mention product names, prices, colors,
  sizes, availability, variants, cart contents, or current surface state only
  when those facts are present in projection, planning context, or a product tool
  result. Model-only catalog facts are a failing drift condition.
- Read-only semantics: read-only means no cart, checkout, payment, shipping,
  admin, fixture mutation, or irreversible side effect. It still allows guarded
  read operations, surface changes, projection refreshes, and canonical path
  updates accepted by the product runtime.
- Stream separation: assistant text stays on the product-agent SSE stream.
  Projection/runtime changes are carried by RouteDeck state events or an
  explicit projection refresh outside assistant prose.
- Shared session/thread: `conversation_id`, LangGraph `thread_id`,
  projection/session state, surface dispatch, route-stream, debug/inspect
  context, and projection version must refer to the same product session.
- Dynamic chips: once a slice claims dynamic action chips, chips must derive from
  current projection/planning context or an agent proposal, refresh after
  projection changes, avoid current-node no-ops unless intentionally labelled as
  refresh/reload, and every visible chip must be chat-doable.
- URL state: graph location uses product paths such as `/browse` and
  `/detail/t-shirt`. Query params are only optional surface/presentation replay
  state, such as `surface_id`.
- Debug visibility: the development debug view must show the current route
  context, planning context, accepted surface intent or operation, public entity
  binding, latest projection version, and full prompt/context while this slice is
  being validated. It can be removed or hidden only in a later explicit slice.

Before this gate is green, name the work honestly as "static projection proof",
"read-only orientation proof", or "planning-context proof". Do not call it a
usable agentic surface.

## Expected Behaviors By Micro-Slice

### M0.1: Capture Current RouteDeck State

Expected behavior:

- No product, framework, package, or UI behavior changes.
- The session produces a truthful baseline of current drift before any reset work.
- Existing unrelated dirty work is identified and left untouched.

Public contract:

- This is an evidence slice only.
- The only allowed outputs are test output, drift-scan output, and implementation notes.

Forbidden behavior:

- No file deletion.
- No source edits.
- No Medusa cleanup disguised as baseline capture.
- No RouteDeck package changes.

Green evidence:

- `git status --short --branch` has been read.
- `tests/test_medusa_reference_slice0.py` has passed or its failure has been reported.
- Medusa later-slice drift has been inventoried before M1 work starts.

### M1.1: Backend Route Surface Is Chat Only

Expected behavior:

- The Medusa backend exposes a normal product-owned chat stream and nothing RouteDeck-shaped.
- A caller can post a user message to the chat stream endpoint.
- Any RouteDeck projection, action, inspect, route-stream, or `/api/routedeck/*` request receives 404.

Public contract:

- Required endpoint: `POST /api/medusa-agent/agent/stream`.
- Optional endpoint: `GET /api/medusa-agent/health` only when tests or local run tooling already use it.
- Response media type for chat stream: `text/event-stream`.

Forbidden behavior:

- No `GET /api/medusa-agent/projection`.
- No `POST /api/medusa-agent/action`.
- No `POST /api/medusa-agent/inspect`.
- No `GET /api/medusa-agent/route-stream`.
- No public endpoint under `/api/routedeck/*`.

Green evidence:

- Route-surface tests prove the chat endpoint exists and all later-slice endpoints are absent.
- Focused route scan finds no later-slice route registration in runtime source.

### M1.2: Backend Has No RouteDeck Or Medusa Store Runtime Imports

Expected behavior:

- The Medusa backend is a chat app, not a RouteDeck adapter and not a commerce runtime.
- Chat service can run without RouteDeck packages, Store API clients, seeded products, cart state, checkout setup, or admin setup.

Public contract:

- Runtime source imports only chat-app dependencies needed for FastAPI, configuration, SSE helpers, LangGraph chat, and model execution.

Forbidden behavior:

- No `routedeck_core` or `routedeck_langgraph` runtime import.
- No `RouteDeck` runtime class or Medusa RouteDeck runtime provider.
- No Store API service import.
- No commerce state, product refs, cart refs, setup state, or agent tool modules.

Green evidence:

- Import-boundary test scans backend runtime source and fails on forbidden imports or references.
- Slice 1 chat tests still pass after later-slice files are removed or quarantined.

### M1.3: SSE Contract Is Real Chat Streaming

Expected behavior:

- Chat produces true SSE frames as the product-owned agent runs.
- The stream carries assistant text as incremental `message_delta` frames when a model is configured.
- Conversation continuity is keyed by `conversation_id`.

Public contract:

- Client sends `conversation_id` and user message to `POST /api/medusa-agent/agent/stream`.
- Backend maps `conversation_id` to LangGraph `configurable.thread_id`.
- Successful stream frame order is `stream_start`, `agent_start`, one or more `message_delta`, `agent_end`, `stream_end`.

Forbidden behavior:

- No completed response split into artificial deltas after execution finishes.
- No deterministic phrase router.
- No command menu response path.
- No RouteDeck state events in the product-agent chat SSE stream.

Green evidence:

- SSE tests parse frames and prove event order, `conversation_id` continuity, and real delta emission from the configured agent path.
- Fake-agent scan has no runtime hits.

### M1.4: Missing OpenAI Key Is Honest Error, Not Fake Agent

Expected behavior:

- When the model cannot run because `OPENAI_API_KEY` is missing, the chat stream reports that operational error honestly.
- The backend does not generate fallback shopping text and does not impersonate the model.

Public contract:

- Missing-key stream emits an SSE `error` frame with code `openai_api_key_missing`.
- The stream may emit setup frames before the error only when those frames do not contain assistant prose.

Forbidden behavior:

- No `message_delta` after a missing-key error.
- No canned assistant greeting used as a fallback model.
- No fallback phrase router.
- No product catalog answer created without a model or an approved fixture tool.

Green evidence:

- Missing-key test clears the environment and proves the error code appears.
- Missing-key test proves assistant deltas are absent.

### M1.5: Frontend Is Chat Only

Expected behavior:

- The first screen is a focused commerce chat experience.
- The user sees transcript history, message composer, send affordance, stream state, and error state.
- The user does not see RouteDeck, Medusa Store API, product cards, cart, checkout, navgraph, diagnostics, inspector, workbench, or command-menu UI.

Public contract:

- Frontend calls only `POST /api/medusa-agent/agent/stream` and optional health tooling.
- UI copy describes shopping assistance in product language, not framework language.

Forbidden behavior:

- No RouteDeck labels.
- No navgraph canvas.
- No product side panel.
- No action chips derived from RouteDeck.
- No diagnostics drawer.
- No cart or checkout control.
- No hardcoded product catalog.

Green evidence:

- Frontend tests prove chat is the primary first-screen experience.
- UI scan proves later-slice terms and controls are absent from runtime UI source.

### M1.6: Slice 1 Anti-Drift Guard

Expected behavior:

- Future edits cannot accidentally turn the chat-only example back into a RouteDeck showcase.
- The guard fails loudly when later-slice runtime behavior returns during M1.

Public contract:

- The guard lives in tests and scans runtime source, not reference docs.
- README language may mention excluded features only as non-goals.

Forbidden behavior:

- No broad scan that fails because docs explain forbidden behavior.
- No weak scan that ignores runtime source.
- No exception list that allows later-slice behavior into M1 runtime.

Green evidence:

- Guard test fails on a temporary runtime reference to a forbidden term and passes after removal.
- Backend and frontend Slice 1 tests pass together.

### M2.1: Core Schema Parity Lock

Expected behavior:

- RouteDeck package consumers can serialize and validate the framework shapes named in the software-on-paper reference.
- Schema names, aliases, and field meanings match `docs/route-deck-reference.md`.

Public contract:

- Pydantic models cover navgraph, capabilities, available entities, surface affordances, surface events, semantic observations, dispatch input, dispatch result, and diagnostics/introspection.
- Alias serialization supports reserved words such as `from`.

Forbidden behavior:

- No Medusa-specific schema fields.
- No cart, checkout, shipping, payment, or admin names in core models.
- No product API route names in core exports.

Green evidence:

- Core contract and projection contract tests pass.
- Framework product-leak scan has no hits.

### M2.2: Core Runtime Projection Helper Lock

Expected behavior:

- Framework runtime helpers build projection output without becoming product graph truth.
- Blocked operations are excluded from legal operations while still explainable through diagnostics.
- Empty entity pools and affordance pools are represented as empty lists, not missing behavior.

Public contract:

- `build_projection(...)` produces `RouteDeckProjection` from manifest/runtime inputs.
- Runtime event helpers emit projection or state payloads for consumers.

Forbidden behavior:

- No product mutation inside projection helpers.
- No Medusa policy inside runtime helpers.
- No hidden operation becoming a product action chip by default.

Green evidence:

- Runtime store contract tests prove projection defaults, navgraph derivation, legal-operation filtering, empty pools, and state event payloads.
- Framework product-leak scan has no hits.

### M2.3: React Type And Store Parity Lock

Expected behavior:

- React consumers can mirror RouteDeck runtime state without the client becoming graph truth.
- The store can apply projections and RouteDeck events, but cannot invent capabilities, commit operations, or create product state.

Public contract:

- React types match Python schema names and field meanings.
- `RouteDeckStore` keeps projection, navgraph, active surface, events, loading/error status, and client-local display state.

Forbidden behavior:

- No client-side capability invention.
- No client-side graph mutation.
- No dispatch result fabrication.
- No Medusa-specific React types.

Green evidence:

- React tests prove schema parity and mirror-only store behavior.
- Framework product-leak scan has no hits in `react/src`.

### M2.4: Package Dry-Run And Public Metadata

Expected behavior:

- RouteDeck can be packaged as a product-neutral open-source alpha candidate.
- A package consumer can install or dry-run the Python and React packages without pulling Medusa product behavior.

Public contract:

- Python packaging metadata, React package metadata, README, license, and notices describe RouteDeck as a framework.
- Package names, exports, and install instructions are product-neutral.

Forbidden behavior:

- No Medusa fixture dependency in RouteDeck packages.
- No product-specific README quickstart as the package quickstart.
- No publication claim before dry-run evidence exists.

Green evidence:

- Python package dry-run succeeds.
- React package dry-run succeeds.
- Public-readiness metadata checks pass.

### M2.5: Product-Neutral Minimal Examples

2026-06-09 recalibration: this slice is deferred unless the user explicitly
asks for a separate product-neutral RouteDeck example. Do not execute M2.5 to
satisfy a Medusa Agent visible-slice request. The active visible slice remains
`examples/medusa-agent/`.

Expected behavior:

- RouteDeck has minimal examples that teach the framework without depending on Medusa.
- Examples demonstrate projection, navgraph, dispatch, state stream, and React consumption using neutral domain data.

Public contract:

- Minimal examples live outside `examples/medusa-agent`.
- Example APIs use generic or example-owned product routes, not `/api/medusa-agent/*`.

Forbidden behavior:

- No Medusa Store API.
- No cart, checkout, product catalog, shipping, payment, or admin concepts.
- No examples that redefine RouteDeck semantics.

Green evidence:

- Minimal example tests or smoke commands pass.
- Framework product-leak scan has no hits.

### M2.6: Framework Full Gate Before Medusa Reintroduction

Expected behavior:

- RouteDeck framework alpha is stable enough that Medusa can consume it as a downstream product example.
- Medusa remains Slice 1 chat-only while this framework gate runs.

Public contract:

- Framework tests, React tests, packaging checks, docs coverage checks, and Medusa Slice 1 guards define the gate.

Forbidden behavior:

- No Medusa RouteDeck reintroduction during M2.
- No hidden Medusa source changes.
- No skipping package or React checks before M3.

Green evidence:

- Full framework gate passes or every failure is documented before stopping.
- User explicitly approves entering M3.

### M3.1: Product-Owned Projection Endpoint Only

Expected behavior:

- Medusa reintroduces RouteDeck as read-only projection output through a Medusa-owned endpoint.
- Chat remains a normal product-agent chat stream.
- The projection can orient current Medusa demo state but cannot execute operations.

Public contract:

- `GET /api/medusa-agent/projection` returns a RouteDeck-derived projection.
- `/api/routedeck/*` remains absent in the Medusa example.
- Projection contains public handles and public entity keys only.

Forbidden behavior:

- No `POST /api/medusa-agent/action`.
- No `POST /api/medusa-agent/inspect`.
- No `GET /api/medusa-agent/route-stream`.
- No Store API write.
- No private Medusa product, variant, cart, or line-item ids in public payloads.

Green evidence:

- Projection-only tests pass with Slice 1 chat tests.
- Private-id scan has no public payload leaks.

### M3.2: Read-Only Navgraph And Product Path Deeplinks

Expected behavior:

- The user can see where the agent/product session is and what locations are reachable.
- Navgraph node selection changes only local inspector focus.
- Browser URL represents product location through path segments, while query parameters hold optional surface or presentation state.

Public contract:

- Canonical paths are `/`, `/browse`, `/detail/:handle`, and `/cart`.
- Query state may include `surface_id` or other presentation replay state.
- The current node path is not encoded as `?rd_node=...` in canonical URLs.
- Deeplinks use public handles or public entity keys only.

Forbidden behavior:

- No navgraph click dispatch.
- No navgraph click URL mutation.
- No private ids in URLs.
- No graph rendered as a command menu.
- No action chips attached to graph nodes.

Green evidence:

- Frontend tests prove read-only graph selection, URL codec behavior, and canonical path use.
- Backend projection tests prove deeplink payloads are public and resumable only when authorized.

### M3.3: Product Surface Rendering Without Dispatch

Expected behavior:

- The active Medusa product surface renders inside the chat/workbench experience.
- Home, browse, detail, and cart surface shells are visible as product surfaces, not diagnostics and not navgraph content.
- Controls that would require dispatch are absent or disabled.

Public contract:

- Surface rendering consumes `projection.surfaces`, active surface metadata, public rendered entities, and presentation state.
- Product surface components emit no runtime operation yet.

Forbidden behavior:

- No `surface_event` dispatch.
- No add-to-cart.
- No checkout.
- No Store API write.
- No detached product side panel presented as the main proof.

Green evidence:

- Frontend tests prove surfaces render in the chat/workbench area and stay separate from navgraph and inspector.
- Frontend tests prove controls cannot dispatch yet.

### M3.4: Surface Event Dispatch For One Read Operation

Expected behavior:

- One product surface click can request one read-only product operation through RouteDeck dispatch.
- The click sends a declared surface affordance, not a private product id and not a hardcoded command.
- Runtime returns a new projection after accepting or rejecting the read request.

Public contract:

- `POST /api/medusa-agent/action` accepts a surface event payload with `surface_id`, `affordance_id`, `event`, `entity_key`, and `projection_version`.
- Runtime resolves the affordance to one allowed read operation such as browse or open detail.

Forbidden behavior:

- No variant selection.
- No cart write.
- No checkout.
- No phrase-router dispatch.
- No UI direct Store API call.

Green evidence:

- Backend test proves affordance resolution, public entity binding, dispatch result, and next projection.
- Frontend test proves UI sends a surface event and never sends a private id.

### M3.5: Surface Event Dispatch For Variant Selection

Expected behavior:

- A user can select a variant through the product surface.
- Variant selection updates product-owned session or presentation state, not cart state.
- Public UI and chat use public variant labels or entity keys while private refs remain internal.

Public contract:

- Variant option carries a public `entity_key`.
- Surface event resolves the public key to the internal variant ref inside Medusa-owned runtime code.

Forbidden behavior:

- No cart add.
- No checkout.
- No private variant id in transcript, URL, projection, or visible UI.
- No direct UI mutation of graph truth.

Green evidence:

- Backend and frontend tests prove variant binding and private-id containment.
- Cart state is unchanged after variant selection.

### M3.6: Planning Context Mirrors Current Surface Capabilities

Expected behavior:

- Anything surface-doable is also chat-doable in principle because the agent receives the same current capabilities and rendered entities.
- The planning context is a product-safe summary for the agent, not diagnostics and not raw graph state.

Public contract:

- Planning context includes current node, active surface, legal product operations, surface affordances, available/rendered public entities, and missing prerequisites.
- Planning context excludes hidden `route.*` operations, blocked operations, private ids, endpoint paths, raw graph state, and diagnostics traces.

Forbidden behavior:

- No agent tool execution added in this slice.
- No leaking diagnostics into public chat.
- No listing internal operation ids as user-facing suggestions.

Green evidence:

- Planning-context tests prove parity with current surface capabilities.
- Tests prove excluded fields stay absent.

### M3.7: Chat Can Invoke One Read Operation And Update Projection

Expected behavior:

- The product agent can use one approved read tool through RouteDeck runtime when the planning context says it is legal.
- The chat path and click path converge on the same runtime boundary for that read behavior.
- The streamed response remains natural assistant text with a product-safe semantic observation.
- The browser-visible projection changes to the resulting product surface, such
  as browse after "show products".
- Product facts in the assistant response are grounded in projection, planning
  context, or tool output.

Public contract:

- Agent tool uses planning context and dispatches through Medusa-owned RouteDeck runtime.
- Product-agent SSE remains `POST /api/medusa-agent/agent/stream`.
- Projection/runtime state is delivered by RouteDeck state event or explicit
  projection refresh outside assistant prose.

Forbidden behavior:

- No direct Store API call from the tool layer.
- No phrase router.
- No command map.
- No cart write.
- No checkout.
- No prose-only claim that a surface opened when projection did not change.
- No product fact absent from projection, planning context, or tool output.

Green evidence:

- Agent-tool test proves the read operation goes through runtime dispatch.
- Browser/frontend test proves the projected surface and path/deeplink state
  update after the chat request.
- Chat SSE tests still prove natural streaming and Slice 1 error behavior.
- Fake-agent scan has no runtime hits.

### M3.8: Cart Add Is The First Write Operation

Expected behavior:

- The first product write is add-to-cart, and it happens only after explicit user intent.
- Cart add requires a selected variant or asks/blocks when the variant is missing.
- Store API unavailable state blocks the write instead of pretending success.

Public contract:

- UI click or chat intent dispatches a typed cart-add operation through Medusa-owned runtime.
- Runtime performs Store API write only after RouteDeck dispatch validation and Medusa product guard validation.
- Public response uses public product labels and cart summary, not private ids.

Forbidden behavior:

- No checkout.
- No payment.
- No shipping.
- No admin mutation.
- No write without explicit click or chat intent.
- No private cart, line, product, or variant id in public UI or chat.

Green evidence:

- Backend tests prove selected-variant requirement, Store API unavailable block, and runtime-only write path.
- Frontend tests prove explicit click behavior and public-id containment.

### M3.9: RouteDeck State Stream Only

Expected behavior:

- RouteDeck state changes are observable through a separate RouteDeck state stream.
- Assistant prose stays on the product-agent chat stream.
- Diagnostics stay out of public chat.

Public contract:

- `GET /api/medusa-agent/route-stream` emits SSE frames for RouteDeck events such as `projection_update`, `operation_started`, `operation_completed`, `graph_transition`, `guard_failure`, `surface_update`, or `runtime_status`.
- RouteDeck state stream frames carry projection/runtime payloads, not assistant text.

Forbidden behavior:

- No assistant `message_delta` on route stream.
- No RouteDeck projection event on product-agent chat stream.
- No diagnostics route or diagnostics UI in this slice.
- No new product operation.

Green evidence:

- State-stream tests prove stream separation by endpoint and event names.
- Chat stream tests still pass.

### M3.10: Read-Only Diagnostics Last

Expected behavior:

- Diagnostics explain current RouteDeck/Medusa runtime state after product behavior is stable.
- Diagnostics are read-only and secondary.
- Diagnostics do not become public chat, action chips, or dispatch controls.

Public contract:

- `POST /api/medusa-agent/inspect` returns sanitized introspection.
- Introspection may include current node, reachable nodes, legal and blocked operations, guards, active surface, navgraph topology, projection version, recent RouteDeck events, and sanitized Medusa API status.

Forbidden behavior:

- No diagnostics mutation.
- No diagnostics dispatch.
- No private ids exposed to shopper-facing UI.
- No diagnostics rendered as the main product proof.

Green evidence:

- Diagnostics tests prove read-only introspection and no dispatch path.
- UI tests prove diagnostics are separate from public chat and product action chips.

### M4.1: Final Test And Drift Gate

Expected behavior:

- RouteDeck is open-source alpha ready as a product-neutral framework.
- Medusa is a credible downstream proof that consumes RouteDeck without redefining it.
- The demo can be explained end-to-end from chat, projection, navgraph, surface, dispatch, planning context, Store API write, state stream, and diagnostics boundaries.

Public contract:

- Framework docs, package metadata, package tests, React tests, Medusa tests, drift scans, and manual smoke checks all describe the same boundary model.

Forbidden behavior:

- No RouteDeck product leakage.
- No Medusa product route served under `/api/routedeck/*`.
- No deterministic command router as the agent.
- No private ids in public UI, chat, or canonical URLs.
- No diagnostics as primary UI.

Green evidence:

- Full RouteDeck Python tests pass or every non-passing result is documented.
- React tests pass or every non-passing result is documented.
- Medusa focused tests pass or every non-passing result is documented.
- Drift scans pass.
- Manual smoke notes prove the final visible behavior matches the reference.

## Execution Rules

- Start every session by reading `critical_prompt.md`, `context.md`, `docs/route-deck-reference.md`, `docs/medusa-agent-reference-app.md`, this plan, `architecture/code-map.md`, and `test_index/README.md`.
- Before each micro-slice, run `git status --short --branch` and preserve unrelated user work.
- Write or tighten the boundary test before implementation.
- Run the focused test and confirm the expected failure when the old behavior exists.
- Implement only enough to pass that micro-slice.
- Run the focused test again.
- Run the micro-slice drift scan.
- Stop after the slice. Do not start the next slice in the same implementation batch unless the user explicitly asks.
- If a slice touches more than one behavior boundary, split it before coding.
- If a slice requires changing both RouteDeck framework source and Medusa product source, split it before coding unless the slice is explicitly a compatibility adapter.

## Universal Drift Scans

Run these after any source micro-slice that touches RouteDeck framework or Medusa example code.

Framework product-leak scan:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
rg -n "Medusa|medusa|SaaStoAgent|Corpus|cart|checkout|payment|shipping|admin|product_ref|variant_ref|/api/medusa-agent" routedeck_core routedeck_langgraph react/src
```

Expected: no hits.

Medusa product-route scan:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
rg -n "/api/routedeck|/api/medusa-agent/(projection|action|inspect|route-stream)|RouteDeck|navgraph|dispatch|diagnostics|Store API|cart|checkout" examples/medusa-agent
```

Expected during M1 Slice 1 reset: no hits except docs/README text explicitly saying those features are absent. Expected after later Medusa reintroduction: only the current micro-slice's allowed endpoint/term appears.

Fake-agent scan:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
rg -n "phrase_router|alias_router|command_router|intent_map|if message|elif message|fake catalog|hardcoded products" examples/medusa-agent
```

Expected: no hits in runtime source. If tests mention banned strings as assertions, keep the scan targeted to runtime source instead of weakening the rule.

## M0: Baseline Only

### Micro-Slice M0.1: Capture Current RouteDeck State

**Files:**

- Read: `critical_prompt.md`
- Read: `context.md`
- Read: `docs/route-deck-reference.md`
- Read: `docs/medusa-agent-reference-app.md`
- Read: `docs/superpowers/plans/2026-06-08-routedeck-open-source-medusa-agent.md`
- Read: `docs/superpowers/plans/2026-06-08-routedeck-medusa-micro-slices.md`
- Read: `architecture/code-map.md`
- Read: `test_index/README.md`

- [ ] **Step 1: Inspect worktree**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core"
git status --short --branch
```

Expected: unrelated dirty files are identified and preserved.

- [ ] **Step 2: Run the reference guard**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
python -m pytest tests/test_medusa_reference_slice0.py -q
```

Expected: `12 passed`. If this fails, do not touch Medusa source.

- [ ] **Step 3: Capture Medusa drift inventory**

Run:

```powershell
rg -n "/api/medusa-agent/(projection|action|inspect|route-stream)|RouteDeck|navgraph|dispatch|diagnostics|Store API|cart|checkout" examples/medusa-agent
```

Expected: current messy later-slice drift is visible. Save the output in the implementation notes for M1.1.

## M1: Medusa Slice 1 Reset

No RouteDeck source changes are allowed in M1. The only goal is to make Medusa a normal app-owned chat agent again.

### Micro-Slice M1.1: Backend Route Surface Is Chat Only

**Files:**

- Modify: `examples/medusa-agent/backend/main.py`
- Modify: `examples/medusa-agent/backend/routes/chat.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice1_chat.py`

- [ ] **Step 1: Add or tighten route-surface tests**

`examples/medusa-agent/backend/tests/test_slice1_chat.py` must assert:

- `POST /api/medusa-agent/agent/stream` exists
- optional `GET /api/medusa-agent/health` exists only if already used by tests
- `GET /api/medusa-agent/projection` returns 404
- `POST /api/medusa-agent/action` returns 404
- `POST /api/medusa-agent/inspect` returns 404
- `GET /api/medusa-agent/route-stream` returns 404
- `/api/routedeck/*` returns 404

- [ ] **Step 2: Run RED**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\backend"
python -m pytest tests/test_slice1_chat.py -q
```

Expected before reset: fail if later-slice routes are still registered.

- [ ] **Step 3: Remove later-slice route registration**

Only register chat and optional health routes in `main.py`. Do not import `routes/routedeck.py`.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_slice1_chat.py -q
```

Expected: Slice 1 route-surface tests pass.

- [ ] **Step 5: Run focused drift scan**

Run:

```powershell
rg -n "/api/medusa-agent/(projection|action|inspect|route-stream)|/api/routedeck" .
```

Expected: no runtime source hit. Test assertions and README non-goal text are allowed.

### Micro-Slice M1.2: Backend Has No RouteDeck Or Medusa Store Runtime Imports

**Files:**

- Modify: `examples/medusa-agent/backend/services/chat_service.py`
- Modify: `examples/medusa-agent/backend/services/graph_builder.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice1_chat.py`
- Delete or quarantine: `examples/medusa-agent/backend/routes/routedeck.py`
- Delete or quarantine: `examples/medusa-agent/backend/services/routedeck_runtime.py`
- Delete or quarantine: `examples/medusa-agent/backend/services/routedeck_manifest.py`
- Delete or quarantine: `examples/medusa-agent/backend/services/routedeck_prompt.py`
- Delete or quarantine: `examples/medusa-agent/backend/services/routedeck_provider.py`
- Delete or quarantine: `examples/medusa-agent/backend/services/planning_context.py`
- Delete or quarantine: `examples/medusa-agent/backend/services/agent_tools.py`
- Delete or quarantine: `examples/medusa-agent/backend/services/medusa_store.py`
- Delete or quarantine: `examples/medusa-agent/backend/services/medusa_setup.py`
- Delete or quarantine: `examples/medusa-agent/backend/services/commerce_state.py`
- Delete or quarantine: `examples/medusa-agent/backend/services/commerce_refs.py`

- [ ] **Step 1: Add import-boundary test**

`test_slice1_chat.py` must scan backend runtime source and assert no imports or references to:

- `routedeck_core`
- `routedeck_langgraph`
- `RouteDeck`
- `MedusaRouteDeckRuntime`
- `medusa_store`
- `commerce_state`
- `agent_tools`

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_slice1_chat.py -q
```

Expected before reset: fail while later-slice modules are referenced or present in runtime imports.

- [ ] **Step 3: Strip backend to chat runtime**

Keep only:

- FastAPI app shell
- config
- SSE protocol helpers
- chat route
- chat stream service
- minimal LangGraph graph builder

Delete later-slice files if they are not needed. If deletion is too risky because of uncommitted user edits, move them into an explicitly ignored `examples/medusa-agent/_quarantine/` folder only after confirming paths stay inside the example.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_slice1_chat.py -q
```

Expected: no forbidden imports remain.

### Micro-Slice M1.3: SSE Contract Is Real Chat Streaming

**Files:**

- Modify: `examples/medusa-agent/backend/core/protocol.py`
- Modify: `examples/medusa-agent/backend/routes/chat.py`
- Modify: `examples/medusa-agent/backend/services/chat_service.py`
- Modify: `examples/medusa-agent/backend/services/graph_builder.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice1_chat.py`

- [ ] **Step 1: Add SSE behavior tests**

`test_slice1_chat.py` must prove:

- response header starts with `text/event-stream`
- stream emits `stream_start`
- stream emits `agent_start`
- stream emits one or more `message_delta` frames on mocked model execution
- stream emits `agent_end`
- stream emits `stream_end`
- `conversation_id` maps to LangGraph `configurable.thread_id`

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_slice1_chat.py -q
```

Expected: fail if the response is NDJSON, non-streamed full text, or not thread-bound.

- [ ] **Step 3: Implement minimal SSE chat path**

The backend must stream from the app-owned chat service. Do not add tools. Do not add RouteDeck. Do not add Medusa Store API.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_slice1_chat.py -q
```

Expected: SSE chat contract passes.

### Micro-Slice M1.4: Missing OpenAI Key Is Honest Error, Not Fake Agent

**Files:**

- Modify: `examples/medusa-agent/backend/core/config.py`
- Modify: `examples/medusa-agent/backend/services/chat_service.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice1_chat.py`

- [ ] **Step 1: Add missing-key test**

`test_slice1_chat.py` must prove that when `OPENAI_API_KEY` is absent:

- stream emits `error`
- error payload includes `code: openai_api_key_missing`
- stream does not emit `message_delta`
- no fallback assistant text is emitted

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_slice1_chat.py -q
```

Expected: fail if deterministic fallback assistant text is emitted.

- [ ] **Step 3: Implement honest missing-key SSE error**

The error text can explain configuration, but it must not pretend to answer as the assistant.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_slice1_chat.py -q
```

Expected: missing-key behavior passes.

### Micro-Slice M1.5: Frontend Is Chat Only

**Files:**

- Modify: `examples/medusa-agent/frontend/src/App.tsx`
- Modify: `examples/medusa-agent/frontend/src/hooks/useSSEChat.ts`
- Modify: `examples/medusa-agent/frontend/src/styles.css`
- Modify: `examples/medusa-agent/frontend/src/App.test.tsx`
- Delete or quarantine: `examples/medusa-agent/frontend/src/hooks/useRouteDeckProjection.ts`
- Delete or quarantine: `examples/medusa-agent/frontend/src/hooks/useRouteDeckStatus.ts`

- [ ] **Step 1: Add frontend reset tests**

`App.test.tsx` must prove:

- first screen has a chat transcript and composer
- sending a message calls `/api/medusa-agent/agent/stream`
- `message_delta` frames append incrementally
- no navgraph, inspector, diagnostics, product card, cart, checkout, dispatch, operation id, RouteDeck text, or route-stream UI is rendered

- [ ] **Step 2: Run RED**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\frontend"
npm test
```

Expected before reset: fail if the current later-slice UI still renders.

- [ ] **Step 3: Implement chat-only frontend**

Render only:

- product-language header
- transcript
- composer
- streaming indicator
- configuration/error message

- [ ] **Step 4: Run GREEN**

Run:

```powershell
npm test
```

Expected: frontend chat-only tests pass.

### Micro-Slice M1.6: Slice 1 Anti-Drift Guard

**Files:**

- Modify: `tests/test_medusa_reference_slice0.py`
- Modify: `examples/medusa-agent/README.md`

- [ ] **Step 1: Add root anti-drift tests**

`tests/test_medusa_reference_slice0.py` must fail if Slice 1 runtime source includes:

- `/api/routedeck`
- `/api/medusa-agent/projection`
- `/api/medusa-agent/action`
- `/api/medusa-agent/inspect`
- `/api/medusa-agent/route-stream`
- `RouteDeck`
- `routedeck_core`
- `navgraph`
- `diagnostics`
- `cart`
- `checkout`
- `phrase_router`
- `alias_router`
- `command_router`

Keep README non-goal text allowed if the test scans runtime paths only.

- [ ] **Step 2: Run RED**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
python -m pytest tests/test_medusa_reference_slice0.py -q
```

Expected before full reset: fail if later-slice runtime drift remains.

- [ ] **Step 3: Update README non-goals**

README must state that Slice 1 is chat only and later RouteDeck/Medusa commerce behavior is intentionally absent.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_medusa_reference_slice0.py -q
cd examples/medusa-agent/backend
python -m pytest tests/test_slice1_chat.py -q
cd ..\frontend
npm test
```

Expected: Slice 1 is clean. Stop here before M2.

## M2: RouteDeck Framework Alpha, No Medusa Reintroduction

M2 works only on framework packages and generic docs/examples. Medusa must remain Slice 1 chat-only throughout M2.

### Micro-Slice M2.1: Core Schema Parity Lock

**Files:**

- Modify: `routedeck_core/models.py`
- Modify: `routedeck_core/__init__.py`
- Modify: `tests/test_core_contract.py`
- Modify: `tests/test_projection_contract.py`

- [ ] **Step 1: Add schema parity tests**

Tests must cover:

- capabilities
- navgraph nodes and edges
- available entities
- surface affordances
- surface interaction events
- semantic observations
- alias serialization for `from` fields

- [ ] **Step 2: Run RED or confirm already GREEN**

Run:

```powershell
python -m pytest tests/test_core_contract.py tests/test_projection_contract.py -q
```

Expected: fail only if schema parity is missing. If already green, record that this micro-slice is a lock-and-document slice and do not add source churn.

- [ ] **Step 3: Implement only missing model/export parity**

Do not add product-specific fields. Do not touch Medusa.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_core_contract.py tests/test_projection_contract.py -q
```

Expected: core schema parity passes.

### Micro-Slice M2.2: Core Runtime Projection Helper Lock

**Files:**

- Modify: `routedeck_core/runtime.py`
- Modify: `tests/test_runtime_store_contract.py`

- [ ] **Step 1: Add runtime helper tests**

Tests must prove:

- `build_projection(...)` defaults manifest capabilities
- `build_projection(...)` derives navgraph from manifest
- blocked operations do not appear in `legal_operations`
- entity and affordance pools default to empty lists
- dispatch state events include state or projection payloads

- [ ] **Step 2: Run focused test**

Run:

```powershell
python -m pytest tests/test_runtime_store_contract.py -q
```

Expected: pass only when helper behavior is locked.

- [ ] **Step 3: Implement minimal helper fixes**

Do not change public schema names unless tests prove drift from `docs/route-deck-reference.md`.

- [ ] **Step 4: Run GREEN and framework product-leak scan**

Run:

```powershell
python -m pytest tests/test_runtime_store_contract.py -q
rg -n "Medusa|medusa|cart|checkout|payment|shipping|admin|/api/medusa-agent" routedeck_core
```

Expected: tests pass and scan has no hits.

### Micro-Slice M2.3: React Type And Store Parity Lock

**Files:**

- Modify: `react/src/types.ts`
- Modify: `react/src/RouteDeckStore.ts`
- Modify: `react/src/RouteDeckProvider.tsx`
- Modify: `react/src/index.ts`
- Modify: `react/tests/*.mjs`
- Modify: `react/tests/*.tsx`

- [ ] **Step 1: Add React parity tests**

Tests must prove:

- store normalization preserves capabilities, navgraph, entities, and affordances
- `receiveEvent(...)` applies RouteDeck state events only
- `connectStream()` subscribes to RouteDeck event types only
- provider hooks expose product-neutral capabilities, entities, affordances, diagnostics, and dispatch
- `RouteDeckStore` mirrors runtime state and does not invent graph truth

- [ ] **Step 2: Run focused React tests**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\react"
npm test
```

Expected: pass only when React parity is locked.

- [ ] **Step 3: Implement missing React parity**

Do not add Medusa-specific hooks, product labels, or product endpoint defaults.

- [ ] **Step 4: Run GREEN and product-leak scan**

Run:

```powershell
npm test
rg -n "Medusa|medusa|SaaStoAgent|Corpus|cart|checkout|payment|shipping|admin|product_ref|variant_ref" src tests package.json
```

Expected: tests pass and scan has no hits.

### Micro-Slice M2.4: Package Dry-Run And Public Metadata

**Files:**

- Modify: `pyproject.toml`
- Modify: `react/package.json`
- Modify: `docs/packaging-roadmap.md`
- Modify: `architecture/components/packaging-public-readiness.md`
- Modify: `THIRD_PARTY_NOTICES.md`

- [ ] **Step 1: Add package readiness checklist to docs**

Docs must state:

- Python package import surface
- optional LangGraph extra
- React package export/declaration policy
- peer dependency policy
- license and third-party notice policy
- when `react/package.json` can remove `private: true`

- [ ] **Step 2: Run package smoke**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
python -m pip install -e .
python -c "from routedeck_core import RouteDeckManifest, RouteDeckProjection; print(RouteDeckManifest.__name__, RouteDeckProjection.__name__)"
cd react
npm test
npm pack --dry-run
```

Expected: Python import works, React tests pass, dry-run package contents are acceptable.

- [ ] **Step 3: Implement metadata/docs fixes only**

Do not reintroduce Medusa. Do not change framework runtime behavior in this slice.

- [ ] **Step 4: Run package smoke again**

Run the same commands from Step 2.

Expected: package readiness smoke passes.

### Micro-Slice M2.5: Product-Neutral Minimal Examples

2026-06-09 recalibration: do not execute this micro-slice during the current
Medusa Agent implementation lane. The attempted `examples/minimal-*` demos were
removed because they caused visible-slice drift. Resume here only after explicit
user approval for generic RouteDeck examples.

**Files:**

- Create: `examples/minimal-langgraph-adapter/README.md`
- Create: `examples/minimal-langgraph-adapter/minimal_graph.py`
- Create: `examples/minimal-langgraph-adapter/test_minimal_graph.py`
- Create: `examples/minimal-fastapi-react/README.md`
- Create: `examples/minimal-fastapi-react/backend/main.py`
- Create: `examples/minimal-fastapi-react/backend/tests/test_app.py`
- Create: `examples/minimal-fastapi-react/frontend/package.json`
- Create: `examples/minimal-fastapi-react/frontend/src/App.tsx`
- Create: `examples/minimal-fastapi-react/frontend/src/App.test.tsx`
- Modify: `docs/minimal-example.md`
- Modify: `README.md`

- [ ] **Step 1: Create product-neutral example tests**

The examples must use generic names such as `home`, `review`, `complete`, `open.review`, and `approve.draft`. Tests must prove projection, dispatch, inspect, and stream behavior without Medusa or commerce terms.

- [ ] **Step 2: Run product-neutral scan**

Run:

```powershell
rg -n "Medusa|medusa|SaaStoAgent|Corpus|cart|checkout|payment|shipping|admin" examples/minimal-langgraph-adapter examples/minimal-fastapi-react docs/minimal-example.md
```

Expected: no hits.

- [ ] **Step 3: Run documented example commands**

Run the commands written in `docs/minimal-example.md`.

Expected: every documented command works. If a command cannot work yet, fix the example or remove the claim.

### Micro-Slice M2.6: Framework Full Gate Before Medusa Reintroduction

**Files:**

- Modify: `test_index/README.md`
- Modify: `context.md`

- [ ] **Step 1: Run full framework gate**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
python -m pytest tests -q
cd react
npm test
cd ..
python scripts/check_doc_coverage.py
```

Expected: root tests pass, React tests pass, doc coverage is clean or warnings are documented.

- [ ] **Step 2: Confirm Medusa is still Slice 1 only**

Run:

```powershell
rg -n "/api/medusa-agent/(projection|action|inspect|route-stream)|/api/routedeck|RouteDeck|navgraph|dispatch|cart|checkout" examples/medusa-agent
```

Expected: no runtime hits. README non-goal text is allowed.

- [ ] **Step 3: Stop**

Do not start M3 until the user explicitly approves RouteDeck reintroduction into Medusa.

## M3: Medusa Reintroduction One Primitive At A Time

M3 starts only after M1 and M2 are green. Every M3 slice keeps Slice 1 chat intact.

### Micro-Slice M3.1: Product-Owned Projection Endpoint Only

**Files:**

- Create: `examples/medusa-agent/backend/services/routedeck_manifest.py`
- Create: `examples/medusa-agent/backend/services/routedeck_runtime.py`
- Create: `examples/medusa-agent/backend/services/routedeck_provider.py`
- Create: `examples/medusa-agent/backend/routes/routedeck.py`
- Modify: `examples/medusa-agent/backend/main.py`
- Create or modify: `examples/medusa-agent/backend/tests/test_slice2_routedeck.py`

- [ ] **Step 1: Add projection-only tests**

Tests must prove:

- `GET /api/medusa-agent/projection` returns RouteDeck-derived projection
- `/api/routedeck/*` remains absent
- no action/dispatch/inspect/route-stream endpoint exists yet
- projection contains no private Medusa ids
- Slice 1 chat endpoint still passes

- [ ] **Step 2: Run RED**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck\examples\medusa-agent\backend"
python -m pytest tests/test_slice1_chat.py tests/test_slice2_routedeck.py -q
```

Expected: fail until projection endpoint is introduced.

- [ ] **Step 3: Implement projection endpoint only**

No dispatch. No inspector. No state stream. No cart writes. No Store API dependency unless projection explicitly blocks unavailable commerce.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_slice1_chat.py tests/test_slice2_routedeck.py -q
```

Expected: Slice 1 chat and projection-only endpoint pass.

### Micro-Slice M3.2: Read-Only Navgraph And Product Path Deeplinks

**Files:**

- Modify: `examples/medusa-agent/backend/services/routedeck_manifest.py`
- Modify: `examples/medusa-agent/backend/services/routedeck_runtime.py`
- Modify: `examples/medusa-agent/frontend/src/App.tsx`
- Modify: `examples/medusa-agent/frontend/src/App.test.tsx`
- Modify: `examples/medusa-agent/frontend/src/styles.css`

- [ ] **Step 1: Add navgraph/deeplink tests**

Tests must prove:

- graph nodes render as read-only inspection controls
- graph selection does not call dispatch
- graph selection does not change browser URL
- `/`, `/browse`, `/detail/:handle`, and `/cart` decode to product-owned locations
- `surface_id` query state is presentation/surface replay only
- `?rd_node=...` is not canonical

- [ ] **Step 2: Run RED**

Run:

```powershell
cd examples/medusa-agent/frontend
npm test
```

Expected: fail until read-only navgraph UI and URL codec exist.

- [ ] **Step 3: Implement read-only navgraph and path codec**

Do not add dispatch. Do not add product cards unless needed as static projected surface content. Do not add cart writes.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
npm test
cd ..\backend
python -m pytest tests/test_slice1_chat.py tests/test_slice2_routedeck.py -q
```

Expected: navgraph/deeplink behavior passes and backend remains projection-only.

### Micro-Slice M3.3: Product Surface Rendering Without Dispatch

**Files:**

- Modify: `examples/medusa-agent/backend/services/routedeck_runtime.py`
- Modify: `examples/medusa-agent/frontend/src/App.tsx`
- Modify: `examples/medusa-agent/frontend/src/App.test.tsx`

- [ ] **Step 1: Add surface rendering tests**

Tests must prove:

- projected home surface renders in chat/workbench area
- projected browse/detail/cart surface shells render as product surfaces without fake behavior
- surfaces are separate from navgraph and inspector
- surface controls are disabled or absent until dispatch slice
- the UI labels or documents this as a static projection/orientation proof, not
  a usable agentic surface
- chat requests are not claimed to have browsed or opened products unless the
  projection actually changes

- [ ] **Step 2: Run RED**

Run:

```powershell
cd examples/medusa-agent/frontend
npm test
```

Expected: fail until surfaces render correctly.

- [ ] **Step 3: Implement surface rendering only**

No surface events. No add-to-cart. No operation dispatch.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
npm test
```

Expected: product surfaces render without dispatch.

### Micro-Slice M3.4: Surface Event Dispatch For One Read Operation

**Files:**

- Modify: `examples/medusa-agent/backend/routes/routedeck.py`
- Modify: `examples/medusa-agent/backend/services/routedeck_runtime.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice3_routedeck_runtime.py`
- Modify: `examples/medusa-agent/frontend/src/App.tsx`
- Modify: `examples/medusa-agent/frontend/src/App.test.tsx`

- [ ] **Step 1: Add single read-operation surface event test**

Use only one operation: product browse or product detail open. Tests must prove:

- UI sends `surface_event`
- runtime resolves declared affordance
- runtime binds public `entity_key`
- runtime returns next projection
- UI never sends private product id

- [ ] **Step 2: Run RED**

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice3_routedeck_runtime.py -q
cd ..\frontend
npm test
```

Expected: fail until the single surface event works.

- [ ] **Step 3: Implement only the read-operation event**

Do not add variant selection. Do not add cart. Do not add checkout.

- [ ] **Step 4: Run GREEN**

Run the same commands.

Expected: one surface event works.

### Micro-Slice M3.5: Surface Event Dispatch For Variant Selection

**Files:**

- Modify: `examples/medusa-agent/backend/services/routedeck_runtime.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice3_routedeck_runtime.py`
- Modify: `examples/medusa-agent/frontend/src/App.tsx`
- Modify: `examples/medusa-agent/frontend/src/App.test.tsx`

- [ ] **Step 1: Add variant selection tests**

Tests must prove:

- variant option has public `entity_key`
- UI emits `surface_event`
- runtime resolves entity binding to opaque private ref internally
- public UI and chat do not show private variant id

- [ ] **Step 2: Run RED**

Run backend and frontend focused tests.

Expected: fail until variant selection exists.

- [ ] **Step 3: Implement variant selection only**

No cart writes in this slice.

- [ ] **Step 4: Run GREEN**

Run backend and frontend focused tests.

Expected: variant selection works without cart writes.

### Micro-Slice M3.6: Planning Context Mirrors Current Surface Capabilities

**Files:**

- Create or modify: `examples/medusa-agent/backend/services/planning_context.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice3_agent_tools.py`
- Modify: `examples/medusa-agent/backend/services/routedeck_prompt.py`

- [ ] **Step 1: Add planning context parity tests**

Tests must prove:

- current node and surface are present
- legal product operations are present
- available/rendered entities are present
- surface affordances are present
- prompt-ready rendered product facts are present when the assistant is allowed
  to answer product questions
- valid `surface_options` are present for any surface the agent may open
- hidden `route.*`, blocked operations, private ids, endpoint paths, diagnostics, and raw graph state are excluded
- assistant-facing context cannot omit rendered surface state while still
  allowing product factual answers

- [ ] **Step 2: Run RED**

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests/test_slice3_agent_tools.py -q
```

Expected: fail until planning context is built.

- [ ] **Step 3: Implement planning context only**

Do not add agent tools yet. The model prompt can read context, but no operation execution is added in this slice.
If chat still cannot drive a runtime operation, this slice remains a
planning-context proof only and must not be called usable.

- [ ] **Step 4: Run GREEN**

Run the same command.

Expected: planning context parity passes.

### Micro-Slice M3.7: Chat Can Invoke One Read Operation And Update Projection

**Files:**

- Modify: `examples/medusa-agent/backend/services/agent_tools.py`
- Modify: `examples/medusa-agent/backend/services/chat_service.py`
- Modify: `examples/medusa-agent/backend/services/graph_builder.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice1_chat.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice3_agent_tools.py`
- Modify: `examples/medusa-agent/frontend/src/App.tsx`
- Modify: `examples/medusa-agent/frontend/src/hooks/useSSEChat.ts`
- Modify: `examples/medusa-agent/frontend/src/hooks/useRouteDeckProjection.ts`
- Modify: `examples/medusa-agent/frontend/src/App.test.tsx`

- [ ] **Step 1: Add one chat-to-projection story test**

Test only one read operation such as browse products. Prove:

- agent tool chooses from planning context
- tool dispatches through runtime
- result streams product-safe semantic observation
- the browser-visible projection changes from home to browse for "show products"
- the canonical browser path becomes `/browse` or the projection refresh carries
  a `location.deeplink.path` of `/browse`
- the projected product surface shows product data from projection/tool output
- debug context shows the route context, planning context, accepted operation or
  `surface_intent`, public entity binding when present, and latest projection
  version
- assistant text remains on product-agent SSE while projection/runtime state is
  delivered by RouteDeck state events or an explicit projection refresh outside
  assistant prose
- no Store API direct call from tool layer
- no phrase router or command map
- no product fact appears in chat unless it exists in projection, planning
  context, or tool output

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_slice1_chat.py tests/test_slice3_agent_tools.py -q
```

Expected: fail until one chat operation works through runtime.

- [ ] **Step 3: Implement one chat read operation and projection application**

Do not add cart writes. Do not add checkout. Do not add admin. Do not carry
projection updates as assistant prose. Use the product-owned runtime result plus
RouteDeck state event or explicit projection refresh to update the visible
surface.

- [ ] **Step 4: Run GREEN**

Run the same command.

Expected: one chat read operation works, the visible projection updates, product
facts are grounded, and Slice 1 chat remains natural.

### Micro-Slice M3.8: Cart Add Is The First Write Operation

**Files:**

- Modify: `examples/medusa-agent/backend/services/medusa_store.py`
- Modify: `examples/medusa-agent/backend/services/commerce_refs.py`
- Modify: `examples/medusa-agent/backend/services/routedeck_runtime.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice3_routedeck_runtime.py`
- Modify: `examples/medusa-agent/frontend/src/App.tsx`
- Modify: `examples/medusa-agent/frontend/src/App.test.tsx`

- [ ] **Step 1: Add first-write tests**

Tests must prove:

- cart add requires explicit UI click or explicit chat intent
- selected variant is required
- write happens only through runtime dispatch
- Store API unavailable blocks the write
- public UI and chat do not expose private cart, line, product, or variant ids

- [ ] **Step 2: Run RED**

Run backend and frontend focused tests.

Expected: fail until cart add works.

- [ ] **Step 3: Implement cart add only**

No checkout. No payment. No shipping. No admin.

- [ ] **Step 4: Run GREEN**

Run backend and frontend focused tests.

Expected: cart add works and no private ids leak.

### Micro-Slice M3.9: RouteDeck State Stream Only

**Files:**

- Modify: `examples/medusa-agent/backend/routes/routedeck.py`
- Modify: `examples/medusa-agent/backend/services/routedeck_runtime.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice2_routedeck.py`
- Modify: `examples/medusa-agent/frontend/src/App.test.tsx`

- [ ] **Step 1: Add state-stream separation tests**

Tests must prove:

- `GET /api/medusa-agent/route-stream` emits RouteDeck event frames
- state stream emits projection/runtime events, not assistant prose
- product-agent chat stream remains `POST /api/medusa-agent/agent/stream`
- diagnostics are not in public chat
- any transitional explicit projection refresh used in M3.7 is either preserved
  as a documented fallback or replaced by named `projection_update` state events
  without changing assistant SSE semantics

- [ ] **Step 2: Run RED**

Run focused backend and frontend tests.

Expected: fail until state stream exists.

- [ ] **Step 3: Implement state stream only**

No diagnostics UI. No new product operations.

- [ ] **Step 4: Run GREEN**

Run focused backend and frontend tests.

Expected: state stream separation passes.

### Micro-Slice M3.10: Read-Only Diagnostics Last

**Files:**

- Modify: `examples/medusa-agent/backend/routes/routedeck.py`
- Modify: `examples/medusa-agent/backend/services/routedeck_runtime.py`
- Modify: `examples/medusa-agent/backend/tests/test_slice2_routedeck.py`
- Modify: `examples/medusa-agent/frontend/src/App.tsx`
- Modify: `examples/medusa-agent/frontend/src/App.test.tsx`

- [ ] **Step 1: Add diagnostics tests**

Tests must prove:

- inspect route returns read-only introspection
- diagnostics can show current node, reachable nodes, legal/blocked operations, guards, active surface, navgraph topology, projection version, and recent events
- diagnostics do not dispatch
- diagnostics do not become public chat
- diagnostics do not become product action chips

- [ ] **Step 2: Run RED**

Run focused backend and frontend tests.

Expected: fail until read-only diagnostics exist.

- [ ] **Step 3: Implement diagnostics only**

No new product operations. No checkout. No admin.

- [ ] **Step 4: Run GREEN**

Run focused backend and frontend tests.

Expected: read-only diagnostics pass.

## M4: Full Acceptance Gate

### Micro-Slice M4.1: Final Test And Drift Gate

**Files:**

- Modify: `test_index/README.md`
- Modify: `context.md`
- Create: `logs/<date>-routedeck-medusa-micro-slices-closeout.md`
- Create: `context_checkpoints/<date>-routedeck-medusa-micro-slices.md`

- [ ] **Step 1: Run full RouteDeck tests**

Run:

```powershell
cd "D:\Dev\AI Projects\agent-core\agent-lab-powered-projects\routedeck"
python -m pytest tests -q
cd react
npm test
cd ..
python scripts/check_doc_coverage.py
```

Expected: all tests pass; doc coverage warnings are fixed or documented.

- [ ] **Step 2: Run full Medusa tests**

Run:

```powershell
cd examples/medusa-agent/backend
python -m pytest tests -q
cd ..\frontend
npm test
```

Expected: all tests pass.

- [ ] **Step 3: Run final drift scans**

Run universal drift scans from this plan.

Expected: no framework product leaks, no fake-agent runtime hits, no disallowed Medusa endpoints for the active slice.

- [ ] **Step 4: Manual smoke**

Smoke only the behavior reached by completed micro-slices. Do not claim checkout, payment, shipping, admin, Docker, or downloadable reference status unless those were implemented in explicit future micro-slices.

For any completed visible product-surface slice, the manual smoke must include:

- start at `/`
- send "show products" in chat
- verify the assistant streams text in real time
- verify the visible projection changes to browse through runtime state, not
  prose-only response text
- verify the URL/path state is `/browse` or the projected deeplink path is
  `/browse`
- send a product-detail request such as "show me the Medusa T-Shirt" only if the
  detail slice is complete
- verify every product fact in chat is present in projection, planning context,
  or tool output
- verify the debug view shows the full context thread, route context, accepted
  operation or surface intent, and latest projection version

## Commit Rule

Commit after every green micro-slice when implementation begins. Commit messages should include the micro-slice id:

- `test(medusa): M1.1 lock chat-only route surface`
- `refactor(medusa): M1.2 strip RouteDeck runtime imports`
- `feat(routedeck): M2.1 lock core schema parity`
- `feat(medusa): M3.1 add product-owned projection endpoint`

If a micro-slice cannot pass in one session, do not continue sideways. Preserve notes, state the exact blocker, and stop.

## Self-Review

Spec coverage:

- M1 protects the chat-only Medusa reset.
- M2 completes RouteDeck framework alpha without Medusa reintroduction.
- M3 reintroduces RouteDeck into Medusa one primitive at a time.
- M4 verifies full acceptance and closeout.

Boundary coverage:

- Every micro-slice names forbidden scope.
- Every micro-slice has a focused test command.
- Every major boundary has a drift scan.
- No micro-slice requires implementing multiple product behaviors at once.

Risk controls:

- The plan stops after M2 before Medusa reintroduction.
- The first write operation is delayed until read projection, navgraph, surfaces, affordances, and planning context are proven.
- The first visible usable surface is delayed until chat-to-projection
  convergence and product-fact grounding are proven in browser behavior.
- Diagnostics are last so they cannot become the product UI by accident.
