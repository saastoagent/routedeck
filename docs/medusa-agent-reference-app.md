# Medusa Agent Reference App

Status: active source of truth
Authority: ADR-006 for runtime ownership; ADR-005 remains active where ADR-006
does not supersede it.

This document defines the implemented standalone Medusa consumer used to prove
RouteDeck's framework boundary. The active code is under
`examples/medusa-agent`; older slice plans are historical implementation
records, not the current runtime contract.

## Purpose

The reference app must prove two things together:

1. RouteDeck is a reusable backend-plus-frontend state framework with durable
   supervision, typed transport, surfaces, private state, and exact navigation.
2. A Medusa buyer agent can stay small, modular, and product-owned: commerce
   code, Store API calls, prompts, and buyer UI never move into RouteDeck.

The proof uses a real protected local Medusa Store API. Product fixtures and
deterministic models are allowed only in isolated tests. The runnable buyer path
does not substitute synthetic products, canned assistant output, heuristic
intent routing, or alternate payment behavior.

## Ownership Boundary

| RouteDeck owns | Medusa app owns |
| --- | --- |
| Immutable application/session/projection/event contracts. | Catalog, cart, checkout, payment, and order declarations. |
| Compilation and exact binding validation. | Async handlers, providers, guards, and recovery policy. |
| One supervised operation/review path for UI and agent. | Typed Store API port, HTTP adapter, wire models, and Medusa IDs. |
| Durable SQLAlchemy state, fencing, events, replay, and private blobs. | Region, country, currency, sales channel, and payment-provider configuration. |
| Shareable/session-bound routes, resume capabilities, and exact history. | Product route-entry resolution and public product-handle validation. |
| Framework runtime assembly, generic user/assistant driver, one HTTP/SSE router, headless client, and named React presentation actions. | Prompt, OpenAI models, user/assistant graph construction, copy, bootstrap choice, and React product components. |

The browser calls `/api/routedeck/*` plus Medusa liveness/readiness. It does not
call Medusa `/store/*`. RouteDeck does not import `medusa_agent` and contains no
commerce operation IDs, URL paths, or wire schemas.

## Developer-Facing Layout

```text
examples/medusa-agent/
  backend/
    medusa_agent/
      api/health.py        # product liveness/readiness only
      features/
        catalog/           # declarations/providers/guards + operation slices
        cart/              # declarations/providers + operation slices
        checkout/          # models, schemas, providers, guards, operation slices
        orders/            # confirmation/reconciliation operation slices
      medusa/client/
        resources/        # catalog/cart/checkout/order resource owners
        http.py           # canonical typed Store facade
        transport.py      # HTTP/auth and delivery classification
        wire.py           # strict response decoding
      agent.py             # product prompt/model/graph composition
      composition.py       # declarative cross-feature app composition
      bindings.py          # typed product dependency injection
      config.py            # strict environment contract
      runtime.py           # product configuration passed to framework openers
      identifiers.py       # canonical cross-feature product identifiers
      session.py           # buyer market, session factory, and initializer
    main.py                # one runtime provider, generic router, health/lifespan
  frontend/src/
    app/                   # bootstrap, chat client, RouteDeck composition
    features/              # buyer product components
    routedeck/             # client and component registry seam
    ui/                    # shell, conversation, composer, navigation/status
  medusa/                  # pinned, repo-local Medusa 2.13.6 demo server
  infra/                   # protected Compose and canonical seed contract
  scripts/                 # protected stack and release verification
```

The Medusa server directory contains only build/runtime source, its exact npm
lock, strict environment configuration, and the canonical demo seed. Compose
uses that local directory for both Medusa services. No sibling `test_targets`
checkout, installed dependency tree, secret, database, or generated manifest is
part of the build context. The protected provisioner continues to own all
seed/reset decisions and uses the real Store APIs plus `pp_system_default`.

The Python backend declares
`routedeck-core[fastapi,langgraph,persistence]` in its own package metadata. Compose
installs the local core distribution and backend together; root extras are not
used to conceal backend runtime requirements.

Adding a product feature normally means declaring its `FeatureSpec`, typed
models/schemas, operation handlers, providers/guards, and React surfaces. The
declarations are composed in `composition.py`, implementations are wired in
`bindings.py`, session callbacks live in `session.py`, and product graphs live
in `agent.py`. `runtime.py` passes those product inputs and strict configuration
to `open_sqlalchemy_routedeck_runtime(...)`; RouteDeck constructs persistence,
runner, navigation, projection, and the generic driver. Each feature keeps one
operation module per buyer action, and `identifiers.py` owns repeated
cross-feature product IDs. Cross-feature behavior is explicit; no global regex
router or hardcoded URL branch infers it.

The Store client is likewise layered: `http.py` exposes the typed facade,
`resources/` owns catalog/cart/checkout/order requests, `transport.py` owns
HTTP/authentication and delivery classification, `wire.py` owns strict response
decoding, and `evidence.py` owns the sanitized measurement port. RouteDeck's
generic FastAPI adapter owns user/assistant request contracts, durable turn
orchestration, replay, cancellation, and SSE framing. The browser requests the
initial system-prompt-authored greeting through the generic typed assistant
endpoint; there is no Medusa entry route.

## Compiled Buyer Graph

`MEDUSA_APP_SPEC` composes four product features.

| Feature | Nodes | Principal operations |
| --- | --- | --- |
| Catalog | `buyer.home`, `catalog.browse`, `catalog.product` | `catalog.list`, `catalog.search`, `catalog.open_product`, `catalog.open_product_by_route`, `catalog.select_variant`, `catalog.continue_shopping` |
| Cart | `cart.summary` | `cart.create`, `cart.add_item`, `cart.open`, `cart.update_item`, `cart.remove_item` |
| Checkout | `checkout.contact`, `checkout.delivery`, `checkout.payment`, `checkout.review` | `checkout.start`, `checkout.save_contact`, `checkout.select_shipping`, `checkout.select_payment`, `checkout.place_order` |
| Orders | `orders.confirmation` | `orders.reconcile` |

Each new guest RouteDeck session runs one product-owned `cart.create` system
operation. It creates a real Medusa cart through the same journaled runner used
by later UI and agent operations. Startup fails if cart initialization cannot be
proved; it does not create an in-memory placeholder.

`checkout.place_order` is an external write with required review and an explicit
`reconcile_unknown_order` directive. A possibly-sent completion is not retried
as if it were safe. `orders.reconcile` re-reads an already observed order and
never completes the cart again.

## Route Contract

| Node | Canonical route | Policy | Entry behavior |
| --- | --- | --- | --- |
| `buyer.home` | `/` | shareable | new-session entry |
| `catalog.browse` | `/products` | shareable | `catalog.list` |
| `catalog.product` | `/products/{product_handle}` | shareable | exact binding to `catalog.open_product_by_route` |
| `cart.summary` | `/cart?resume_handle=...` | session-bound | current cart only |
| `checkout.contact` | `/checkout/contact?resume_handle=...` | session-bound | current guest checkout |
| `checkout.delivery` | `/checkout/delivery?resume_handle=...` | session-bound | current shipping state |
| `checkout.payment` | `/checkout/payment?resume_handle=...` | session-bound | current payment state |
| `checkout.review` | `/checkout/review?resume_handle=...` | session-bound | current reviewed cart |
| `orders.confirmation` | `/orders/{confirmation_handle}/confirmation?resume_handle=...` | session-bound | current verified order |

The product route declares `RouteEntrySpec` and `RouteParameterBinding` instead
of duplicating route parsing in the app. RouteDeck performs structural/canonical
validation and dispatches the declared operation. `OpenProductByRouteHandler`
uses the typed Store client to resolve the public handle. A missing or ambiguous
product fails as a typed product/contract result.

Session-bound routes require the guest cookie plus an unexpired capability tied
to the exact session, node, and route parameters. Browser history carries the
server's unique entry ID. Back, forward, cancel, reload, and `popstate` reconcile
through `/api/routedeck/navigation`; the browser cannot manufacture a canonical
checkout or confirmation entry.

## Surface Contract

The app declares product surfaces with exact public prop schemas and registers
the matching React components in `frontend/src/routedeck/surfaces.tsx`.
Important surfaces include:

- `buyer.welcome`
- `catalog.product_grid`
- `catalog.product_detail`
- `cart.summary`
- `checkout.contact_form`
- `checkout.shipping_options`
- `checkout.payment_method`
- `checkout.order_review`
- `checkout.review`
- `checkout.recovery`
- `orders.confirmation`

Buyer, catalog, cart, checkout, and order frames/data surfaces are stable so
their canonical public state survives exact history restoration. Diagnostic
surfaces use the default ephemeral lifecycle and reset with projection changes.

React components do not call operation IDs directly when a surface affordance
exists. `RouteDeckSurfaceHost` resolves `browse_products`, `open_product`,
`add_item`, `start_checkout`, `save_contact`, `select_shipping`,
`select_payment`, `propose_order`, `reconcile_order`, and `continue_shopping`
through the compiled surface contract.

The active and review slots render in the buyer conversation/workbench. Review
accept/reject controls use RouteDeck's versioned review API; order placement is
not treated as complete when the proposal is merely staged.

The collapsible right sidebar mounts RouteDeck's generic `RouteDeckNavGraph`.
Opening it renders the complete sitemap: all nine buyer nodes and every
compiled transition, with current and reachable nodes highlighted. The overlay
can expand fullscreen and exposes node routes, deep-link policy, surface slots,
currently legal operations, and outgoing outcomes without adding
Medusa-specific graph logic or hardcoded edges to the frontend.

## Private Checkout

`checkout.contact_form` and the reloadable `checkout.order_review` surface
declare the same server-only `PrivateFormBindingSpec` with:

- public handle prop `form_handle`;
- exact top-level checkout field allowlist.

The public projection contains only the opaque handle, revision/completeness,
field names, billing choices, and country choices. The private channel returns
revision `0` and `{}` for an authorized untouched form. On save it validates the
allowed shape, encrypts the value, and atomically commits the private draft and
blob with the RouteDeck session.

The `SaveContactHandler` reads the decrypted form through an injected
`CheckoutPrivateFormReader`, validates typed email/address/billing/country
contracts, and calls `MedusaStoreClient.set_checkout_contact`. Private values
do not enter public projection, model context, events, diagnostics, or URLs.
The review binding is read-only in product behavior; it authorizes the current
node to hydrate the private delivery summary after a review-page reload without
copying those values into public state.

## Typed Medusa Client

`MedusaStoreClient` is the business port. Its methods cover region/product
discovery, cart creation/read/mutation, contact, shipping, payment
initialization, cart completion, and independent order retrieval.

`HttpMedusaStoreClient` is the canonical facade. Its catalog, cart, checkout,
and orders resource objects own endpoint-specific requests; the shared
transport owns base URL/authentication/delivery classification and `wire.py`
owns response shapes. Together they:

- decodes into typed immutable product/cart/order/payment models;
- requires exact success resources and discriminators;
- sanitizes provider, transport, protocol, and business failures;
- records whether an external request was not sent, possibly sent, or received;
- never returns raw exception text, raw response bodies, or private identifiers
  to the public runtime.

Feature handlers receive the protocol through dependency injection. Tests can
use explicit test ports, but the runnable product path always uses the HTTP
adapter and configured Medusa source of truth.

## Payment And Order Completion

The protected fixture enables exactly `pp_system_default`. The buyer UI labels
this as the system/manual demo payment method. It is an explicit local-demo
provider, not a production payment claim.

Payment selection checks the current Medusa provider allowlist and configured
provider ID, creates/uses the real payment collection, initializes a real
payment session, and refreshes the cart. No generic `payment succeeded` value is
invented locally.

Before order placement, RouteDeck stages a review from refreshed checkout
facts. Acceptance revalidates that the proposal is current, calls cart complete
once, binds the resulting private order ID behind an opaque public order handle,
and independently calls `get_order`. The confirmation surface is projected only
from that verified order.

## LangGraph And Chat

`agent.py` owns the buyer prompt, model, and LangChain `create_agent(...)`
composition. The graph topology remains unchanged and product-owned.
`RouteDeckMiddleware` reconstructs durable conversation turns, injects only the
current default-deny public context, and filters tools to legal operations.
`RouteDeckToolWrapper` executes each tool through the same runner as UI
affordances. Parallel tool calls are disabled and rejected.

The tool-enabled buyer model makes one semantic decision: respond directly or
emit a structured call to one currently legal tool. There is no pre-agent turn
classifier. RouteDeck owns legality and supervision; the Medusa buyer model
owns current-turn relevance and conversation behavior.

`runtime.py` supplies `RouteDeckLangGraphGraphs` containing the product's
tool-enabled user graph and no-tool assistant-initiation graph.
`RouteDeckLangGraphDriverFactory` constructs the framework-owned driver and
translates LangGraph model/tool events into the small `RouteDeckAgentDriver`
contract. No Medusa module calls `astream_events(...)` or owns HTTP routes,
turn leases, conversation persistence, replay, or SSE envelopes.
`POST /api/routedeck/chat` and
`POST /api/routedeck/conversation/assistant-turn` stream RouteDeck-owned events such as
`stream_start`, `conversation_snapshot`, `assistant_delta`, `review_required`,
`assistant_end`, `chat_error`, and `stream_end`. The authoritative interaction
handshake remains `GET /api/routedeck/events`; `turn_started` makes projected
surfaces inert before the driver can expose a tool-produced surface. Assistant
prose without a completed tool result and matching RouteDeck projection is not
a commerce state change.

Assistant initiation sends no `HumanMessage`, emits no `user_message` frame,
persists only the assistant turn, and rejects tools/review. The browser loads
canonical history first and requests this turn only when history is empty. It
requires `assistant_end` plus `stream_end: completed`, synchronizes versions,
and reloads canonical conversation; a conflict reloads instead of inventing a
greeting.

React conversation presentation uses named actions for snapshot, user message,
assistant text/reset/finalization, review, completion, and failure. The network
hook retains abort/retry/discard/resync ownership, and
`RouteDeckObservableState` remains canonical session/projection state.

`OPENAI_API_KEY` plus the required `OPENAI_BUYER_MODEL` and
`OPENAI_ENTRY_MODEL` settings select the live OpenAI path. No key means no
chat agent is composed; the chat endpoint returns a visible 503 unavailable
failure and full application readiness remains false. Liveness and direct
non-model API checks remain available, but the Compose-gated buyer frontend
waits for a callable agent. The two roles do not inherit from one another. There is
no model fallback or canned response.

## API Planes

Product-owned:

- `GET /api/medusa-agent/health`
- `GET /api/medusa-agent/ready`

Generic RouteDeck:

- `GET /api/routedeck/contract`
- `POST /api/routedeck/sessions`
- `GET /api/routedeck/session`
- `GET /api/routedeck/conversation`
- `POST /api/routedeck/chat`
- `POST /api/routedeck/conversation/assistant-turn`
- `POST /api/routedeck/navigation`
- `POST /api/routedeck/dispatch`
- `POST /api/routedeck/reviews/{review_id}/accept`
- `POST /api/routedeck/reviews/{review_id}/reject`
- `GET /api/routedeck/events`
- `GET|PUT /api/routedeck/private-forms/{form_id}`
- `GET /api/routedeck/inspect`

Generic routes contain no product names or Medusa behavior. Medusa supplies
product graphs/prompts/models and the frontend bootstrap chooses when to call
the typed assistant operation; RouteDeck owns the driver, transport, and
durable conversation state. `main.py` mounts exactly one generic router from a
runtime provider plus the product health router.

`health` is process liveness. `ready` verifies the RouteDeck store and real
Medusa dependency and returns `503` until the buyer application can serve real
requests. The frontend container gates startup on readiness, not liveness.

## Mutation Identity And Explicit Retry

`POST /api/routedeck/sessions` requires a caller-generated `request_id`. Every
later state-changing request carries a globally unique `request_id`; versioned
mutations also carry `expected_session_version`. RouteDeck durably records
session creation, navigation, private-form saves, chat turns, and ordinary
operation attempts with their exact request fingerprint and committed result.

An exact replay returns the recorded result without calling Medusa or the model
again. Reusing an ID with a different payload fails with `request_id_reused`.
When the browser cannot know whether a request committed, it retains the exact
ID and payload and exposes an explicit retry/abandon choice. It does not
automatically issue a second commerce write.

Private-form saves advance the canonical session version and append a
`private_form_changed` event containing only public revision metadata. The form
ID and private values remain absent from the public event log.

## Fail-Loud Configuration

`Settings.from_env()` reads `examples/medusa-agent/.env.local` and explicit
process overrides. Medusa resource IDs and secrets have no product-code
defaults. The live runtime validates that:

- the configured region exists exactly once;
- the configured country belongs to that region;
- the Store client returns typed values;
- the configured payment provider is offered;
- the RouteDeck database and encryption key are supplied;
- every feature binding is exact.

Missing or contradictory configuration aborts startup or the affected request.
The app does not switch to a fixture, default region, alternate provider,
in-memory store, local model, or empty catalog.

## Protected Local Stack

Local Windows execution is authoritative. From the RouteDeck project directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Provision
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Up -Services all
```

URLs:

- frontend: `http://127.0.0.1:5198`
- agent API: `http://127.0.0.1:8098`
- Medusa: `http://127.0.0.1:9100`

The provisioner verifies the Compose project name, protected volume labels,
database name, sentinel row, canonical seed keys, generated manifest hash,
generated credentials, and SQLite deletion scope. Re-running `Provision` on a
valid stack validates it without reseeding.

Stop without deleting fixture state:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Down
```

## Reset Fixture Rule

The protected fixture is seeded local/demo Medusa data only. No validation lane
depends on production Medusa data.

`Reset` is destructive and must be explicitly intended. It first requires a
complete, correctly labeled protected stack and exact sentinel/manifest
evidence. It then removes only the named demo volumes and
`examples/medusa-agent/.demo-data`, and reprovisions the canonical seed. It must
restore the fixture to the seed state; it must not guess recovery for partial or
unlabeled resources.

## Validation And Release Truth

Framework, frontend, real-Medusa, browser, coverage, and release commands are
indexed in [`../test_index/README.md`](../test_index/README.md). The consolidated
release harness is `examples/medusa-agent/scripts/release-verify.ps1`.

A valid release run must prove:

1. framework correctness;
2. boundary and adapter integrity;
3. real commerce source of truth;
4. browser, buyer-agent, and developer experience.

The browser proof must cover the full guest flow, reload, shareable and
session-bound deep links, exact history restoration, review, confirmation,
recovery behavior, and absence of browser Store API traffic. The live buyer
agent portion requires an explicit `OPENAI_API_KEY`. Missing credentials fail
that gate; a test-only scripted model cannot satisfy it.

After explicit approval of the protected destructive reset, the local command
is:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\release-verify.ps1 -ResetProtectedDemo
```

No live-model release pass is claimed by this document. Only a current,
sanitized release report can make that claim.
