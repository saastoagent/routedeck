# Medusa Agent

This is the standalone RouteDeck reference consumer: a full local guest-buyer
application backed by a real Medusa Store API. RouteDeck supplies generic state,
supervision, persistence, transport, navigation, and React primitives. This app
supplies all commerce behavior, API calls, prompts, and buyer-facing surfaces.

The example is source-complete inside this repository. Its Compose stack builds
the pinned Medusa 2.13.6 server from `medusa/`; it does not require an
`agent-core/test_targets` checkout, preinstalled `node_modules`, copied secrets,
or external runtime data. `package-lock.json` and the digest-pinned Node image
make the server build independently reproducible.

## Implemented Buyer Flow

The product-owned flow is:

1. create one real guest cart for the RouteDeck session;
2. browse or search the Store catalog;
3. open a shareable product route and select an exact in-stock variant;
4. add, update, or remove real cart line items;
5. enter session-bound guest checkout;
6. save contact, shipping, and billing values through the encrypted private-form
   channel;
7. choose an authoritative Medusa shipping option;
8. initialize the configured `pp_system_default` payment provider;
9. review the current cart and explicitly accept or reject order placement;
10. complete the cart once, independently re-read the order, and show a
    session-bound confirmation;
11. continue shopping without discarding the durable session history.

`pp_system_default` is Medusa's system/manual provider in this protected demo.
It is explicit demo payment behavior, not a hidden mock or a fallback payment
path.

## Boundaries

Backend business code is feature-local:

```text
backend/medusa_agent/
  features/
    catalog/             # declarations/providers/guards + operation slices
    cart/                # cart declarations/providers + operation slices
    checkout/            # models/schemas/guards/providers + operation slices
    orders/              # confirmation/reconciliation operation slices
  medusa/client/
    protocol.py          # typed MedusaStoreClient port
    http.py              # endpoint-oriented Store API facade
    transport.py         # HTTP/auth and delivery classification
    wire.py              # strict response decoding helpers
    evidence.py          # sanitized measured-call evidence port
    models.py            # strict wire and result models
    errors.py            # product client contract errors
  api/
    chat.py              # durable chat-turn orchestration
    chat_contract.py     # request and dependency contracts
    chat_events.py       # model-event decoding and SSE frames
    chat_replay.py       # mutation replay and HTTP boundary
  composition.py         # declarative cross-feature app composition
  bindings.py            # typed product dependency injection
  runtime_factory.py     # runner, navigation, and persistence assembly
  runtime.py             # environment-specific live assembly
  agent.py               # prompt, model, and LangGraph agent composition
  identifiers.py         # canonical cross-feature product identifiers
```

Feature declarations are composed once in `composition.py`, implementations
are wired once in `bindings.py`, and framework runtime construction lives in
`runtime_factory.py`. Product behavior is organized under each feature's
`operations/` package, one module per buyer operation; cross-feature IDs live in
`identifiers.py`. No global regex router or hardcoded URL branch infers product
behavior.

The adjacent `medusa/` directory is infrastructure for the real demo Store API,
not RouteDeck framework code or buyer-agent business logic. It owns the pinned
Medusa package graph, strict server configuration, and canonical protected demo
seed. `infra/` owns the sentinel, seed fingerprint, manifest, and scoped
provision/reset policy.

There are no Store URLs or HTTP calls in feature operations. Operations depend
on the typed `MedusaStoreClient` protocol. `HttpMedusaStoreClient` is the
endpoint facade; its transport, wire decoding, and evidence responsibilities
are separate modules. Together they return sanitized typed failures and
preserve delivery evidence as
`not_sent`, `possibly_sent`, or `response_received`. The browser calls only the
product API and generic RouteDeck API; it never calls `/store/*` directly.

RouteDeck owns:

- the canonical guest session and exact browser-history entry identities;
- legal operations, version checks, idempotency, leases, review, and events;
- stable/ephemeral surface state and default-deny public projection;
- shareable versus session-bound routes and resume capabilities;
- encrypted private-form persistence and generic HTTP/SSE transport.

The Medusa app owns:

- catalog/cart/checkout/order feature declarations and business bindings;
- Store API transport and all Medusa IDs behind opaque public handles;
- region, country, sales-channel, and payment-provider configuration;
- the buyer prompt, OpenAI model, product chat endpoint, and UI components;
- recovery decisions such as order reconciliation after an uncertain write.

## Route And Surface Contract

Shareable routes:

- `/`
- `/products`
- `/products/{product_handle}`

The product detail route uses a declarative `RouteEntrySpec` that binds the
exact `product_handle` segment to `catalog.open_product_by_route`. RouteDeck
parses the route structurally; the product handler resolves the handle through
the typed Store client.

Session-bound routes:

- `/cart?resume_handle=...`
- `/checkout/contact?resume_handle=...`
- `/checkout/delivery?resume_handle=...`
- `/checkout/payment?resume_handle=...`
- `/checkout/review?resume_handle=...`
- `/orders/{confirmation_handle}/confirmation?resume_handle=...`

A session-bound link is accepted only when the guest cookie, route parameters,
unexpired resume capability, and current RouteDeck session agree. Browser
back/forward restores an exact server-owned history entry; it does not infer a
new commerce action from the URL.

Product components register against compiled `SurfaceSpec.component` names in
`frontend/src/routedeck/surfaces.tsx`. Surface affordances dispatch declared
RouteDeck operations. Checkout contact uses `PrivateFormBindingSpec` to
authorize one projected form handle and an exact top-level field allowlist.
Untouched authorized forms load as revision `0`; the first real save atomically
stores revision `1` and an encrypted private blob. Private values never enter
the frontend contract, public projection, event stream, inspection response, or
model context.

The order-review surface declares the same server-only binding so a true
review-page reload can rehydrate the private delivery summary. That binding
does not expose the form schema or values through the frontend contract.

## LangGraph Agent

The app owns a normal LangChain `create_agent(...)` graph. RouteDeck does not
generate or replace that graph. `RouteDeckMiddleware` projects the current
public state and only currently legal tools into each model call;
`RouteDeckToolWrapper` sends tool calls through the same supervised runner used
by surface affordances.

Durable conversation turns live in the RouteDeck session and are reconstructed
for each request. Product chat streams from `POST /api/medusa-agent/chat`.
Canonical RouteDeck state events remain on `GET /api/routedeck/events`.
Chat SSE responses are `private, no-store, no-transform`; if interruption
persistence fails, the stream terminates as `outcome_unknown` and the browser
retains the exact request for explicit retry/resync.

There is no fallback model, phrase router, canned assistant reply, synthetic
catalog, or browser-side commerce substitute.

## Local Windows Quickstart

Requirements:

- local Docker Desktop/Engine with Compose;
- PowerShell;
- an `OPENAI_API_KEY` for the complete ready buyer-agent stack.

No separate Medusa repository or starter checkout is required. The first
provision builds `examples/medusa-agent/medusa` locally and installs exactly the
dependency graph recorded in its lockfile.

From the RouteDeck project directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Provision
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Up -Services all
```

Open `http://127.0.0.1:5198`.

| Service | URL |
| --- | --- |
| Buyer frontend | `http://127.0.0.1:5198` |
| Agent API | `http://127.0.0.1:8098` |
| Liveness | `http://127.0.0.1:8098/api/medusa-agent/health` |
| Readiness | `http://127.0.0.1:8098/api/medusa-agent/ready` |
| Medusa | `http://127.0.0.1:9100` |

`Provision` creates the protected volumes, canonical seed, database sentinel,
seed fingerprint, generated Store credentials, and local RouteDeck encryption
configuration. On an already valid stack it verifies those identities and does
not rerun the seed.

Inspect or stop the stack with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Status
powershell -NoProfile -ExecutionPolicy Bypass -File .\examples\medusa-agent\scripts\demo-stack.ps1 -Action Down
```

`Down` retains the protected volumes. Do not use `Reset` for ordinary startup.
`Reset` is destructive: it validates the project identity, expected volume
labels, database sentinel, generated manifest, and SQLite deletion scope before
deleting and reprovisioning only this fixture.

## Configuration

Provisioning writes the required local values to
`examples/medusa-agent/.env.local`. Product code has no defaults for Medusa
resource IDs or secrets. Required runtime fields are:

```text
MEDUSA_BASE_URL
MEDUSA_PUBLISHABLE_KEY
MEDUSA_REGION_ID
MEDUSA_COUNTRY_CODE
MEDUSA_SALES_CHANNEL_ID
MEDUSA_PAYMENT_PROVIDER_ID
ROUTEDECK_DATABASE_URL
ROUTEDECK_STATE_ENCRYPTION_KEY
OPENAI_BUYER_MODEL
OPENAI_ENTRY_MODEL
OPENAI_TURN_POLICY_MODEL
```

`OPENAI_API_KEY` is optional for API-process liveness but required for live
chat and full application readiness. When it is absent,
`POST /api/medusa-agent/chat` fails visibly with `503 dependency_unavailable`,
`GET /api/medusa-agent/ready` returns `503`, and the Compose-gated frontend
waits. Add the key to `.env.local` and recreate the application services to
enable the complete buyer agent. The three model roles are explicit and
required; none inherits another role's configuration. Do not add a fallback
credential or model.

The live-model release smoke also requires this key. This README does not claim
that smoke has passed.

## APIs

Product-owned endpoints:

- `GET /api/medusa-agent/health`
- `GET /api/medusa-agent/ready`
- `POST /api/medusa-agent/chat` (`text/event-stream`)

Generic RouteDeck endpoints mounted by the product:

- `GET /api/routedeck/contract`
- `POST /api/routedeck/sessions`
- `GET /api/routedeck/session`
- `POST /api/routedeck/navigation`
- `POST /api/routedeck/dispatch`
- `POST /api/routedeck/reviews/{review_id}/accept`
- `POST /api/routedeck/reviews/{review_id}/reject`
- `GET /api/routedeck/events`
- `GET|PUT /api/routedeck/private-forms/{form_id}`
- `GET /api/routedeck/inspect`

The generic plane contains no Medusa route names or commerce behavior.

Session creation is an idempotent mutation and requires
`{"request_id":"<globally-unique-id>"}`. Dispatch, navigation, review,
private-form, and chat writes likewise use caller-owned request identities.
After an outcome-unknown transport failure, the frontend retains the exact
request ID and payload for an explicit retry; it does not auto-retry or replace
the ID. The same ID with different input is rejected.

## Development Checks

Backend:

```powershell
python -m pytest examples/medusa-agent/backend/tests -q
```

Frontend:

```powershell
pnpm --filter @routedeck/medusa-agent test
pnpm --filter @routedeck/medusa-agent typecheck
pnpm --filter @routedeck/medusa-agent build
```

The real-Medusa integration tests require the provisioned local stack and its
actual Store API configuration. See
[`../../test_index/README.md`](../../test_index/README.md) for the release gates
and [`../../docs/medusa-agent-reference-app.md`](../../docs/medusa-agent-reference-app.md)
for the architecture contract.
