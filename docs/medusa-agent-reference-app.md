# Medusa Agent Reference App Spec

Status: active source of truth
Date: 2026-05-28

## Purpose

The Medusa agent reference app is the future product-specific RouteDeck adoption
example. Slice 0 is documentation and public-readiness groundwork only: it names
the product boundary, records the RouteDeck/API split, and prevents RouteDeck
from absorbing Medusa behavior before the example is authorized.

RouteDeck remains product-neutral, but the Medusa example must expose public
HTTP routes in Medusa-owned language. The reference app should make RouteDeck
contracts visible through product-owned state/projection/action/inspect
endpoints while keeping Medusa commerce behavior in Medusa-owned handlers.
Medusa owns the agent, public API routes, commerce routes, domain state,
prompts, seeded data, UI copy, and product workflow behavior. RouteDeck provides
reusable contracts, runtime/projection models, React state helpers, optional
LangGraph integration helpers, and diagnostics primitives consumed by the
Medusa app.

RouteDeck framework terms in this spec follow `docs/route-deck-reference.md`.

This file supersedes `docs/propertydesk-reference-app.md` as the active
product-specific reference-app source of truth.

## Current Recalibration Directive

The runnable Medusa example is the active RouteDeck adoption proof. It must
remain Medusa-owned and chat-first while RouteDeck is introduced in very small,
auditable steps.

The current implemented checkpoint is a transitional state: normal app-owned
commerce chat plus a read-only RouteDeck projection grounding layer. It is not
pure Slice 1, because pure Slice 1 has no RouteDeck projection, Route Map,
Inspector, or `surface_id`. It is not a usable product-surface slice until the
Visible Surface Usability Gate below is green:

- First-screen assistant chat turn, `POST /api/medusa-agent/agent/stream`, true
  SSE assistant deltas, process-local conversation state, live model execution
  when configured, and explicit missing-key errors.
- Product-owned `GET /api/medusa-agent/projection` that returns RouteDeck
  projection/navgraph data for orientation only.
- Projection-backed Route Map and Inspector that can update local inspector
  focus without dispatching, navigating, mutating graph state, or changing the
  browser URL.
- Product-owned canonical paths: `/`, `/browse`, `/detail/t-shirt`, and
  `/cart`. Optional `surface_id` query state may restore the active surface, but
  the path remains the canonical public location.

The current target still excludes action dispatch, inspect routes, route-stream,
action chips derived from RouteDeck legal operations, commerce product
surfaces, Medusa Store API reads, cart writes, checkout, payment, shipping,
admin, diagnostics panels, private Medusa IDs, `rd_node` canonical links, and
RouteDeck-prefixed public routes.

Future slices remain design contracts until explicitly implemented by a bounded
slice. They do not authorize the runnable example to jump ahead of the current
chat-first, read-only-projection/orientation proof.

## Visible Surface Usability Gate

The Medusa example must not call a projected product surface "usable" until the
chat path and surface path converge on the same product-owned RouteDeck runtime
boundary.

Required before any visible surface slice is described as usable:

- From `/`, a normal chat request such as "show products" resolves through
  product-agent planning context, dispatches a typed read operation or surface
  intent through the Medusa-owned runtime, and updates the visible projection to
  the browse surface.
- From `/browse`, a normal chat request such as "show me the Medusa T-Shirt"
  binds a public entity key or handle from projection/planning context and
  updates the visible projection to the detail surface.
- Assistant product facts are grounded in projection, planning context, or a
  product tool result. The model must not invent product names, colors, sizes,
  prices, availability, or cart contents from general language-model priors.
- The address bar uses the product path for graph location, such as `/browse` or
  `/detail/t-shirt`. Query params are only optional surface or presentation
  state, such as `surface_id=detail.product_detail`.
- Projection updates caused by chat do not travel as assistant prose. The product
  chat SSE stream carries assistant text, while RouteDeck state events or an
  explicit projection refresh carries the next projection.
- `conversation_id`, LangGraph `thread_id`, projection/session state,
  surface-event dispatch, route-stream, debug/inspect context, and projection
  version all refer to the same product session.
- Dynamic chips, once introduced, derive from current projection/planning context
  or an agent proposal, refresh after projection changes, avoid ordinary
  current-node no-ops, and remain chat-doable.
- The debug/context view shows the current route context, planning context,
  accepted `surface_intent` or operation, public entity binding, and latest
  projection version. It may temporarily show the full system prompt during
  development, but must be removable before public release.

Before that gate is green, the visible UI is only a static projection or
orientation proof. It may show read-only context, but it must not claim that the
agent has browsed, opened, selected, compared, or changed product state unless
the projection actually changed.

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

The future Medusa app has one public, product-owned API surface that consumes
RouteDeck contracts internally.

### Medusa Product API

The product API is for commerce behavior, chat, and RouteDeck-derived state:

- `GET /api/medusa-agent/state`
- `GET /api/medusa-agent/route-manifest`
- `GET /api/medusa-agent/route-snapshot`
- `GET /api/medusa-agent/projection`
- `POST /api/medusa-agent/action`
- `POST /api/medusa-agent/agent/stream`
- `POST /api/medusa-agent/inspect`
- `GET /api/medusa-agent/route-stream`

These routes belong to the Medusa example app. They expose shopping, checkout,
admin, reset, chat, projection, runtime inspection, and product diagnostics in
Medusa language.

No public Medusa example endpoint is served under `/api/routedeck/*`. Generic
RouteDeck APIs can exist in other framework deployments, but this product
example must not turn RouteDeck-prefixed routes into a Medusa product surface.
Early slices may expose dispatch as a guarded product-owned contract endpoint
without executing product operations.

## Architecture Boundary

- Medusa owns the LangGraph agent and its streaming endpoint.
- Medusa owns product operations, authorization, seeded demo data, UI language,
  and domain-specific workflow choices.
- RouteDeck owns generic package contracts for manifest, snapshot, projection,
  dispatch, inspect, stream, React state, and diagnostics.
- RouteDeck packages must not vendor Medusa source or special-case Medusa domain
  behavior.
- Agent execution is not a RouteDeck operation.

## Slice Contracts

Each implementation slice must keep public product routes and reusable RouteDeck
contracts clear.

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

Purpose: connect local/demo Medusa readiness and introduce RouteDeck through
explicit product-owned projection, navgraph, and path-state endpoints. Slice 2
does not execute action dispatch.

Current implemented subset: M3.1/M3.2 introduces only product-owned
`GET /api/medusa-agent/projection` and projection-backed read-only Route
Map/Inspector behavior. It does not introduce local/demo Medusa data access,
state/action/inspect/route-stream endpoints, action chips, dispatch, product
surfaces, Store API calls, cart writes, or setup readiness UI.

Implementation plan:
`docs/superpowers/plans/2026-06-02-medusa-agent-slice2.md`.

Expected API split:

- Medusa setup and chat stay under `/api/medusa-agent/*`.
- RouteDeck-derived manifest/projection/snapshot payloads are served under
  `/api/medusa-agent/*` only when the micro-slice explicitly introduces them.
- `/api/routedeck/*` must not exist in the Medusa example app.
- `POST /api/medusa-agent/action`, inspect routes, route-stream routes, and
  operation execution belong to later explicit micro-slices. They are not part
  of the projection/navgraph/URL checkpoint.

Done when:

- Passive product setup readiness is visible without operation lists, blocked
  future actions, dispatch traces, or diagnostics in the default product UI.
- Product-owned endpoints expose RouteDeck-derived projection/navigation payloads
  without exposing a RouteDeck-prefixed public API.
- Medusa-specific policy remains in the Medusa adapter/handlers.

### Slice 3: Product Browse, Variant Selection, And Cart

Purpose: make browse/select/cart behavior share one dispatch path across UI and
agent tools.

Implementation plan:
`docs/superpowers/plans/2026-06-03-medusa-agent-slice3.md`.

Required behavior:

- Product list/detail/cart surfaces derive from RouteDeck projection backed by
  the local/demo Medusa Store API.
- The projected navgraph renders as an actual graph of RouteDeck nodes and
  edges. It is orientation context for the agent/user, not a list of operation
  IDs or dispatch traces.
- The projected navgraph includes a stable `home` node that centers the Medusa
  buyer-agent experience before browse/detail/cart work begins.
- The visible navgraph is read-only. Selecting graph nodes can update a local
  inspector, but graph clicks must not dispatch operations, navigate, mutate
  graph state, or change the browser URL.
- Product action chips render in the Medusa chat/assistant experience,
  following the Corpus quick-action pattern, from product-safe projected
  operations, capabilities, affordances, or agent proposals. Hidden `route.*`
  operations and graph nodes must not become product chips.
- The first visible Medusa agent state is an assistant chat turn with starter
  action chips when `home` projects legal actions. It is not an empty-state
  panel, landing page, debugger, or graph-first placeholder.
- The Medusa product surface is embedded in the chat stream, following the
  Corpus workspace pattern. It remains separate from the navgraph and
  inspector, but it is not a detached product side panel. Product cards, home
  CTAs, variant buttons, and cart buttons emit `surface_event` payloads. They
  must not be implemented as navgraph clicks.
- Same-node operations are not ordinary next-action chips. For example,
  `catalog.list` may be a legal operation while the current node is `browse`,
  but the browse surface should not show a "Browse products" chat chip unless
  Medusa intentionally labels it as a refresh/reload action.
- The Medusa side rail includes a read-only inspector that summarizes current
  node, reachable locations, action labels, entity labels, affordance labels,
  deeplink, and edge/capability metadata without exposing private IDs or
  RouteDeck operation IDs to shoppers.
- Product-owned deeplinks are visible in the browser address bar. A URL such as
  `/detail/t-shirt` may be copied and pasted to resume the same projected
  product-detail state when the local demo runtime can authorize and resolve the
  public product handle. `/` is the home node, `/browse` is product browsing,
  and `/cart` is the cart node. Legacy query links such as
  `/?rd_node=detail&rd_product=t-shirt` may be accepted for compatibility, but
  the canonical visible deeplinks follow the Corpus path-owned codec pattern.
- Deeplink URLs must use public product handles or public entity keys only. They
  must not expose private Medusa product IDs, variant IDs, cart IDs, RouteDeck
  operation IDs, or hidden dispatch payloads.
- UI clicks and agent tools share the same RouteDeck dispatch boundary: UI
  clicks emit `surface_event` payloads resolved through surface affordances,
  while agent tools dispatch typed operations with rendered entity keys; no
  phrase router, hardcoded products, or fake catalog is allowed.
- A Medusa-owned planning context built from RouteDeck projection plugs into the
  agent system prompt so the model understands current capabilities and
  rendered entities before choosing tools.
- Chat requests that imply a visible product surface change, such as "show
  products", "open the t-shirt", or "compare both", must either update the
  browser-visible projection through that shared runtime boundary or explicitly
  say the current slice cannot do it yet. Assistant prose without a projection
  update is not accepted as completion.
- Product facts in chat must match the product state available in projection or
  product tool output. If projection says the T-Shirt has `Natural`, `Black`, and
  `Navy` colors, public chat must not answer `White` or `Heather Grey`.
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
- The Medusa example serves public endpoints under `/api/routedeck/*`.
- `/api/routedeck/medusa/*` or another product-specific RouteDeck route appears.

## Public Readiness Gates

Before RouteDeck publication work proceeds, maintain:

- MIT license metadata for Python and React packages.
- A top-level `LICENSE`.
- A top-level `THIRD_PARTY_NOTICES.md`.
- Packaging docs that call out licensing and third-party notice checks before
  PyPI or npm publication.
