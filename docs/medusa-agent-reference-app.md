# Medusa Agent Reference App Spec

Status: active source of truth
Date: 2026-05-28

## Purpose

The Medusa agent reference app is the future product-specific RouteDeck adoption
example. Slice 0 is documentation and public-readiness groundwork only: it names
the product boundary, records the RouteDeck/API split, and prevents RouteDeck
from absorbing Medusa behavior before the example is authorized.

RouteDeck remains product-neutral, but it should not hide behind the product
API. The reference app should make the RouteDeck API plane visible as its own
generic state/projection/dispatch/inspect surface while keeping Medusa commerce
behavior in Medusa-owned handlers. Medusa owns the agent, commerce routes,
domain state, prompts, seeded data, UI copy, and product workflow behavior.
RouteDeck provides reusable contracts, runtime/projection models, React state
helpers, optional LangGraph integration helpers, and diagnostics primitives
consumed by the Medusa app.

RouteDeck framework terms in this spec follow `docs/route-deck-reference.md`.

This file supersedes `docs/propertydesk-reference-app.md` as the active
product-specific reference-app source of truth.

## Slice 0 Boundary

Slice 0 may add this spec, public-readiness metadata, and drift checks. It must
not create `examples/medusa-agent`, backend code, frontend code, Docker setup,
seeded data, runtime scripts, or end-to-end flows.

## Reset Fixture Rule

The reference app is allowed to automate commerce and admin behavior only against
a seeded local/demo Medusa fixture. Every slice that introduces Medusa writes
must preserve an explicit reset path. That reset path must restore the fixture to
the seed state. No slice may depend on production Medusa data, external payment
settlement, external shipment purchase, or irreversible third-party side effects.

Invariant: reset must restore the fixture to the seed state.

Slice-specific implications:

- Slice 1 uses in-memory chat state only, so reset means clearing the demo
  conversation state.
- Slice 2 may connect setup state to local/demo Medusa, but setup writes remain
  app-owned and resettable.
- Slices 3 through 5 may create carts, orders, fulfillment records, and admin
  mutations only inside the seeded local/demo Medusa fixture.
- Slice 6 must document and verify the one-command reset path before the
  reference app is considered downloadable.

## Public Contracts

The future Medusa app has two public API planes.

### Medusa Product API

The product API is for commerce behavior and chat:

- `GET /api/medusa-agent/state`
- `POST /api/medusa-agent/action`
- `POST /api/medusa-agent/agent/stream`
- `POST /api/medusa-agent/inspect`

These routes belong to the Medusa example app. They expose shopping, checkout,
admin, reset, chat, and product diagnostics in Medusa language.

### RouteDeck API

The RouteDeck API is allowed, expected, and encouraged to be separate from the
product API when it stays a framework/projection contract rather than the
product experience:

- `GET /api/routedeck/manifest`
- `GET /api/routedeck/snapshot`
- `GET /api/routedeck/projection`
- `POST /api/routedeck/dispatch`
- `POST /api/routedeck/inspect`
- `GET /api/routedeck/stream`

Those routes must stay generic. They expose RouteDeck concepts such as manifest,
runtime state, projection, dispatch validation, events, and introspection. They
must not become Medusa-specific routes such as `/api/routedeck/medusa/*`, and
they must not contain Medusa business policy. Early slices may expose dispatch
as a guarded contract endpoint without executing product operations.

## Architecture Boundary

- Medusa owns the LangGraph agent and its streaming endpoint.
- Medusa owns product operations, authorization, seeded demo data, UI language,
  and domain-specific workflow choices.
- RouteDeck owns generic APIs and package contracts for manifest, snapshot,
  projection, dispatch, inspect, stream, React state, and diagnostics.
- RouteDeck packages must not vendor Medusa source or special-case Medusa domain
  behavior.
- Agent execution is not a RouteDeck operation.

## Slice Contracts

Each implementation slice must keep the two API planes clear.

### Slice 0: Spec, Licensing, And Reset

Purpose: establish this source-of-truth spec, public-readiness metadata, reset
fixture rules, and drift checks.

Done when:

- PropertyDesk is superseded as the active reference-app plan.
- RouteDeck API and Medusa product API responsibilities are explicit.
- License and third-party notice metadata exist.
- No runnable Medusa example code exists yet.

### Slice 1: Normal Commerce Chat Agent, No RouteDeck

Purpose: prove the example starts as a normal app-owned commerce chat agent
before RouteDeck is introduced.

User experience:

- `hi` receives a natural greeting.
- `what can you help with?` explains shopping help in product language.
- `show me products` may ask whether the user wants browsing help, but it must
  not expose RouteDeck terms.
- `I want to buy a t-shirt` collects size/color/style intent naturally.
- `not sure` leads to clarifying questions, not a command menu.

Allowed implementation:

- Medusa app-owned chat UI.
- Medusa app-owned `POST /api/medusa-agent/agent/stream`.
- A stripped-down `foundation-agent` style SSE/LangGraph architecture.
- OpenAI-backed agent execution with default model `gpt-5-mini`; missing
  `OPENAI_API_KEY` must emit an error and must not produce fallback assistant
  text.
- In-memory demo conversation state.

Not allowed:

- RouteDeck runtime, manifest, projection, dispatch, or inspect.
- Medusa API calls that require seeded fixture setup.
- UI controls pretending to be RouteDeck operations.

### Slice 1 Implementation Contract

Slice 1 must create the smallest runnable app shell for normal commerce chat. It
must not introduce RouteDeck, Medusa API integration, checkout, cart mutation, or
admin behavior.

Implementation plan: `docs/superpowers/plans/2026-05-28-medusa-agent-slice1.md`.

File layout:

- `examples/medusa-agent/README.md`: run commands, Slice 1 scope, smoke prompts,
  and explicit no-RouteDeck/no-Medusa-runtime statement.
- `examples/medusa-agent/backend/main.py`: FastAPI app that exposes the Slice 1
  chat stream endpoint and any local health endpoint needed by tests.
- `examples/medusa-agent/backend/app.py`: compatibility export for tests that
  imports `app` from `main.py`.
- `examples/medusa-agent/backend/core/config.py`: OpenAI/model config
  with default model `gpt-5-mini`.
- `examples/medusa-agent/backend/core/protocol.py`: true SSE helpers based on
  the stripped `foundation-agent` event pattern.
- `examples/medusa-agent/backend/routes/chat.py`: `text/event-stream` endpoint
  for `POST /api/medusa-agent/agent/stream`.
- `examples/medusa-agent/backend/services/graph_builder.py`: minimal no-tool
  LangGraph commerce agent builder.
- `examples/medusa-agent/backend/services/chat_service.py`: app-owned stream
  orchestration with OpenAI execution and explicit missing-key errors.
- `examples/medusa-agent/backend/requirements.txt`: exact latest-stable
  backend pins checked on 2026-05-28: `fastapi==0.136.3`,
  `httpx==0.28.1`, `langchain-openai==1.2.2`, `langgraph==1.2.2`,
  `pytest==9.0.3`, and `uvicorn==0.48.0`.
- `examples/medusa-agent/backend/tests/test_slice1_chat.py`: backend tests for
  greeting, capability explanation, product-browse clarification, t-shirt
  intent, uncertain input, SSE shape, default model, missing-key error, and
  RouteDeck absence.
- `examples/medusa-agent/frontend/src/App.tsx`: first-screen chat UI, not a
  landing page and not a RouteDeck/debugger shell.
- `examples/medusa-agent/frontend/src/hooks/useSSEChat.ts`: stripped
  `foundation-agent` style SSE client for the app-owned stream endpoint.
- `examples/medusa-agent/frontend/src/App.test.tsx`: frontend tests for sending
  prompts, rendering streamed assistant text, and not rendering RouteDeck
  operation/debugger UI.
- `examples/medusa-agent/frontend/package.json`: exact latest-stable frontend
  pins checked on 2026-05-28: `@vitejs/plugin-react@6.0.2`,
  `react@19.2.6`, `react-dom@19.2.6`, `typescript@6.0.3`,
  `vite@8.0.14`, `@testing-library/jest-dom@6.9.1`,
  `@testing-library/react@16.3.2`, `jsdom@29.1.1`, and `vitest@4.1.7`.

HTTP surface:

- `POST /api/medusa-agent/agent/stream` is the only required Slice 1 product
  endpoint.
- Optional `GET /api/medusa-agent/health` is allowed for local smoke checks.
- `/api/routedeck/*` must not exist in Slice 1.
- `GET /api/medusa-agent/state`, `POST /api/medusa-agent/action`, and
  `POST /api/medusa-agent/inspect` remain future endpoints unless the Slice 1
  implementation needs a read-only local chat-state endpoint for tests.

Stream payload shape:

The response must be true Server-Sent Events with `Content-Type:
text/event-stream`, not NDJSON. The primary stream event is
`event: "message_delta"`:

```text
event: stream_start
data: {"conversation_id":"...","model":"gpt-5-mini"}

event: agent_start
data: {"agent_name":"medusa-commerce-agent"}

event: message_delta
data: {"content":"Hi, I can help you browse demo products."}

event: agent_end
data: {}

event: stream_end
data: {}
```

The backend may also emit `event: "error"` with a product-language error message
for malformed requests and `: ping` keepalive comments for long-running streams.
It must not emit RouteDeck operation ids, graph nodes, dispatch traces, Medusa
private ids, payment ids, or admin credentials.

LLM and LangGraph:

- Slice 1 uses a minimal app-owned LangGraph agent.
- The graph has one commerce agent node and no tools.
- The default OpenAI model is `gpt-5-mini`.
- `MEDUSA_AGENT_MODEL` may override the model locally.
- `OPENAI_API_KEY` enables the live OpenAI path.
- Tests must pass through mocked execution without network access; Slice 1 must
  not include fallback assistant responses.
- Use `langgraph==1.2.2` and `langchain-openai==1.2.2`.
- Use `InMemorySaver` and map `conversation_id` to LangGraph
  `configurable.thread_id`.
- Use LangGraph `stream_events(..., version="v2")` or
  `astream_events(..., version="v2")` as the graph-to-SSE source for
  compatibility with the installed LangGraph runtime.
- Stream `message_delta` from graph message text/token output, not by splitting
  a completed `invoke()` response after the graph finishes.

State/data:

- Conversation state is in-memory and process-local.
- Reset for Slice 1 is clearing or recreating that in-memory conversation state.
- No database, Medusa container, seeded product catalog, payment provider, or
  admin credential is required.

Acceptance commands:

- `python -m pytest examples/medusa-agent/backend/tests -q`
- `npm test` from `examples/medusa-agent/frontend`
- Browser smoke: send `hi`, `what can you help with?`, `show me products`, `I
  want to buy a t-shirt`, and `not sure`; confirm each response reads like a
  normal shopping assistant, not a command menu.

### Slice 2: Medusa Connection And RouteDeck Projection

Purpose: connect local/demo Medusa and introduce RouteDeck as an explicit
separate API plane.

Implementation plan:
`docs/superpowers/plans/2026-06-02-medusa-agent-slice2.md`.

Expected API split:

- Medusa setup and chat stay under `/api/medusa-agent/*`.
- RouteDeck manifest/projection/snapshot/inspect/stream may be served under
  `/api/routedeck/*`.
- RouteDeck dispatch may exist only as a guarded contract endpoint in this
  slice. It must reject operation execution and must not drive product behavior.

Done when:

- Passive product setup readiness is visible without operation lists, blocked
  future actions, dispatch traces, or diagnostics in the default product UI.
- RouteDeck APIs expose generic RouteDeck payloads.
- Medusa-specific policy remains in the Medusa adapter/handlers.

### Slice 3: Product Browse, Variant Selection, And Cart

Purpose: make browse/select/cart behavior share one dispatch path across UI and
agent tools.

Implementation plan:
`docs/superpowers/plans/2026-06-03-medusa-agent-slice3.md`.

Required behavior:

- Product list/detail/cart surfaces derive from RouteDeck projection backed by
  the local/demo Medusa Store API.
- UI clicks and agent tools dispatch the same typed RouteDeck operations; no
  phrase router, hardcoded products, or fake catalog is allowed.
- RouteDeck context plugs into the agent system prompt so the model understands
  current capabilities before choosing tools.
- Private Medusa IDs stay out of public transcript text.
- Missing variant/cart prerequisites are blocked or requested before dispatch.
- Cart writes require explicit user intent from chat or direct UI action.

### Slice 4: Checkout, Payment, Shipping, And Order Completion

Purpose: complete the buyer path against local/test Medusa providers.

Required behavior:

- Collect demo address/contact input.
- Select shipping option.
- Initialize/select fake payment provider.
- Complete cart/order.
- Show order confirmation.
- Require confirmation before irreversible demo writes.

No real payment gateway, external shipping purchase, or production data is
allowed.

### Slice 5: Admin Operations, Fulfillment, And Destructive Sandbox Writes

Purpose: demonstrate admin/operator capability against seeded local data.

Required behavior:

- Inventory/order reads are visible and explainable.
- Fulfillment/shipment updates and product/inventory mutations use typed
  operations.
- Cancel/refund/delete-style demo actions require explicit confirmation.
- Every destructive action creates visible dispatch and diagnostic evidence.
- Reset returns the fixture to the seed state.

### Slice 6: Diagnostics, Docker, And Downloadable Run

Purpose: make the reference example easy to run, inspect, reset, and evaluate.

Required behavior:

- One-command Docker/local path.
- Seeded credentials and reset instructions.
- Smoke prompts and known limits.
- Read-only diagnostics that explain RouteDeck state, gates, dispatches, Medusa
  API calls, and private state without becoming the primary UI.

## Agent Authority Matrix

| Operation family | Agent authority | Required guard |
| --- | --- | --- |
| Greeting and shopping clarification | Respond directly | No RouteDeck before Slice 2 |
| Product browse/read | Execute or navigate when legal | Use projected operation readiness once RouteDeck exists |
| Variant/cart mutation | Execute after required inputs are bound | Dispatch typed operation; no hidden IDs in transcript |
| Checkout completion | Propose and confirm | Confirm address/payment/shipping summary |
| Admin mutation | Propose and confirm | Require admin capability and diagnostic event |
| Destructive sandbox action | Confirm explicitly | Resettable fixture and visible dispatch evidence |
| Auth/session/setup/reset | Use app-owned route/form | Do not model as ordinary RouteDeck dispatch unless explicitly designed |

## Future Example Location

When Slice 1 or later authorizes implementation, the intended location is:

```text
agent-lab-powered-projects/routedeck/examples/medusa-agent/
```

Until then, that directory must not exist.

## Drift Signals

- A superseded product plan is described as the active flagship reference app.
- Medusa commerce routes are documented as RouteDeck-owned product routes.
- RouteDeck is described as hosting, exposing, or owning the Medusa agent.
- Medusa domain source appears in `routedeck_core`, `routedeck_langgraph`, or
  `react/src`.
- `examples/medusa-agent` is implemented before Slice 1 or later approval.
- `/api/routedeck/*` is banned outright instead of kept as a generic RouteDeck
  API plane.
- `/api/routedeck/medusa/*` or another product-specific RouteDeck route appears.

## Public Readiness Gates

Before RouteDeck publication work proceeds, maintain:

- MIT license metadata for Python and React packages.
- A top-level `LICENSE`.
- A top-level `THIRD_PARTY_NOTICES.md`.
- Packaging docs that call out licensing and third-party notice checks before
  PyPI or npm publication.
