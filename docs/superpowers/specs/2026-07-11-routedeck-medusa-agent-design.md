# RouteDeck And Medusa Buyer Agent Design

Status: Design approved and self-reviewed; awaiting written-spec approval
Date: 2026-07-11
Scope: Replace the existing `examples/medusa-agent` implementation with a clean standalone RouteDeck-backed Medusa buyer agent.

## Objective

Build RouteDeck and a Medusa buyer agent together through consumer-driven vertical slices. RouteDeck must become a reusable backend-and-frontend framework, while the Medusa application remains a light, developer-friendly consumer containing commerce behavior, product integrations, and product UI only.

The delivered buyer flow is:

```text
discover -> browse -> product detail -> variant selection -> cart
  -> address -> shipping -> payment -> order review -> place order
  -> order confirmation
```

The flow uses actual local Medusa Store APIs and resettable seeded Medusa data. Demo payment uses Medusa's configured `pp_system` provider and is visibly identified as demo/manual payment. It is not a fake success fallback. All implementation, service execution, and release verification run locally unless the user explicitly changes that decision.

## Approved Strategy

Use consumer-driven lockstep development. Every vertical slice introduces only the RouteDeck capability immediately consumed by the matching Medusa buyer behavior. A RouteDeck-only test result is never sufficient; each slice must leave the corresponding Medusa backend and browser behavior working.

The existing Medusa example is replaced in place. Its code is not the architectural foundation. Before replacement, preserve only verified behavioral contracts, useful real Medusa API evidence, and relevant acceptance tests.

## Ownership Boundary

### RouteDeck owns

- complete agentic interaction and session state
- navgraph definition, validation, reachability, and transitions
- current node, route parameters, navigation history, back, forward, and cancel
- active, frame, peer, detail, form, review, and diagnostic surface mechanics
- surface lifecycle, affordance resolution, and deep-link primitives
- scoped agent context and legal-tool exposure
- visible entity bindings and operation-specific real-ID allowlists
- guard evaluation, blocked feedback, needs-input state, and review lifecycle
- pending-operation and tool-execution status
- state needed across turns, navigation, reconnects, or reloads
- tool-result observations and interaction evidence
- projections, projection versions, events, SSE framing, diagnostics, and frontend synchronization
- headless frontend store/client primitives and React integration primitives

### Medusa owns

- agent prompt, model selection, personality, and conversation behavior
- products, variants, prices, inventory, carts, shipping, payment sessions, and orders
- Medusa authentication, publishable keys, and product API configuration
- actual commerce tool implementations and external side effects
- product-specific context providers, business guards, and surface props
- product surface components, language, styling, and visual design

RouteDeck may retain state-scoped references and projections of Medusa facts, but Medusa remains authoritative for commerce records. RouteDeck never contains commerce logic or Medusa API paths.

Only the Medusa composition root may wire RouteDeck, LangGraph, FastAPI, persistence, and Medusa implementations together. It must not contain generic projection, navigation, surface, event, or supervision algorithms.

## Navgraph And LangGraph

The RouteDeck navgraph and the LangGraph execution graph are separate graphs.

| Graph | Responsibility | Owner |
| --- | --- | --- |
| RouteDeck navgraph | Application interaction states, legal transitions, operations, surfaces, deep links, recovery, and projected UI state | RouteDeck |
| LangGraph execution graph | Model calls, message flow, agent/tool loop, and transient per-turn execution state | Medusa agent runtime |

RouteDeck manages its navgraph as a typed state machine:

```text
current RouteDeck state + supervised operation + typed outcome
  -> validated next RouteDeck state
```

RouteDeck does not require LangGraph to define or execute the navgraph.

LangGraph state is not a second durable session authority. RouteDeck owns the durable conversation, interaction, operation, and navigation records; the Medusa runtime reconstructs each LangGraph turn from that RouteDeck-owned history.

## LangGraph Integration

The primary integration does not accept and secretly mutate an arbitrary `StateGraph`. RouteDeck exposes an optional `routedeck_langgraph` adapter at stable LangGraph extension points.

For standard LangChain agents backed by LangGraph, `RouteDeckMiddleware`:

1. loads the current RouteDeck session and derives the scoped model context before each model call
2. injects only the allowlisted, non-sensitive RouteDeck context
3. exposes only currently legal product tools
4. supervises every structured tool call before execution
5. short-circuits blocked, needs-input, or review-required calls
6. delegates allowed execution to the shared operation runner with the LangGraph handler as its executor callback
7. reports typed success or failure results back to RouteDeck

For raw `StateGraph` applications, the adapter supplies explicit model-node and tool-call wrappers. It does not rewrite graph topology. A raw `ToolNode` can use the adapter's asynchronous tool-call wrapper.

One generic `RouteDeckOperationRunner` owns request identity, session leasing, supervision, review, execution claims, journaling, and transition application. Both LangGraph middleware and HTTP/UI dispatch delegate to it. The runner invokes an injected `OperationExecutor` port only after supervision allows the call; the Medusa composition root binds each operation to exactly one registered product handler. The runner contains no Medusa code or API paths. Review acceptance resumes the recorded attempt through the same runner.

RouteDeck core never invokes Medusa APIs directly. The injected host executor invokes the bound product handler, and the runner observes its typed result.

## Feature-Composed Navgraph Authoring

A flat global list of nodes, edges, actions, surfaces, and mappings does not scale. RouteDeck applications are composed from namespaced feature modules such as catalog, cart, checkout, and orders.

Each feature owns:

- its rich node definitions
- operations and typed inputs
- surfaces and affordances
- scoped context and entity providers
- product guard bindings
- internal transitions and typed outcomes
- recovery behavior and feature-level tests

Each feature exports an immutable, serializable `FeatureSpec` and separate runtime `FeatureBindings`. Compilation consumes only specifications. Application composition binds provider, guard, and handler references and validates one-to-one completeness. The application supplies the shared `OperationExecutor` separately. Generated frontend artifacts never contain callables, Python import paths, or backend-only configuration.

A node is a typed interaction aggregate with references to:

- identity, title, hierarchy, and node kind
- declarative route template and deep-link policy
- context and entity providers
- allowed operations and capabilities
- active/frame/review surfaces
- navigation, dirty-state, cancel, and recovery policies
- public presentation and diagnostic metadata

Typed node and operation objects are referenced directly; product code does not duplicate string IDs. Internal feature transitions stay with the feature. Cross-feature transitions are explicit at application composition.

The compiled application validates duplicate routes, dangling references, missing providers, invalid surface bindings, unreachable nodes, undeclared outcomes, and invalid hierarchy. It produces the backend navgraph, frontend client contract, deep-link templates, surface catalog, and executable test paths from one source.

## Code And Package Boundaries

### Python packages

```text
routedeck_core/
  app/
  contracts/
  state/
  context/
  supervision/
  navigation/
  projection/
  ports/
  errors.py

routedeck_langgraph/
  middleware.py
  tool_wrapper.py
  model_context.py

routedeck_fastapi/
  router.py
  sse.py
  dependencies.py

routedeck_sqlite/
  store.py
  schema.py
  migrations.py
  codec.py

routedeck_testing/
  conformance.py
  factories.py
```

`routedeck_core` has no dependency on LangGraph, FastAPI, React, or Medusa. Optional integration packages depend on the core. Products depend on the core and the adapters they select. Reverse product dependencies are prohibited.

### Frontend packages

```text
@routedeck/core
  store
  event reducer
  client
  route and deep-link codec
  selectors
  contracts

@routedeck/react
  provider and hooks
  surface host and registry
  navigation and deep-link components
  review and needs-input primitives
  status and error primitives
  navgraph inspector

@routedeck/testing
  store and component test helpers
```

The headless store remains independent of React. React bindings subscribe to the store and render framework primitives. Medusa registers concrete product components rather than implementing surface lifecycle or state synchronization.

### Medusa application

```text
examples/medusa-agent/
  backend/
    medusa_agent/
      composition.py
      config.py
      agent.py
      medusa/client/
        protocol.py
        http.py
        models.py
        errors.py
      features/
        catalog/
        cart/
        checkout/
        orders/
      api/
        chat.py
        health.py

  frontend/
    src/
      app/
      routedeck/
      features/
        catalog/
        cart/
        checkout/
        orders/
      ui/
```

Medusa HTTP access is isolated behind a typed `MedusaStoreClient` protocol and one HTTP adapter. Only that adapter owns endpoint templates, headers, base URLs, serialization, and transport errors. Product handlers call typed methods such as `list_products`, `get_product`, `create_cart`, `add_line_item`, `update_line_item`, `remove_line_item`, `set_address`, `list_shipping_options`, `set_shipping_option`, `list_payment_providers`, `initialize_payment`, `complete_cart`, and `get_order`.

## Buyer-Flow State Model

The first release supports guest checkout. Customer accounts, authentication, saved addresses, order history, administration, refunds, returns, and fulfillment management are outside this release.

### Nodes And Primary Surfaces

| Node | Route template | Primary surface | Purpose |
| --- | --- | --- | --- |
| `buyer.home` | `/` | `buyer.welcome` | Start or resume the buyer journey |
| `catalog.browse` | `/products` | `catalog.product_grid` | Discover, search, and browse products |
| `catalog.product` | `/products/{product_handle}` | `catalog.product_detail` | Inspect a product and select a real variant |
| `cart.summary` | `/cart` | `cart.summary` | Inspect and modify the real Medusa cart |
| `checkout.contact` | `/checkout/contact` | `checkout.contact_form` | Capture guest email, shipping address, and billing choice |
| `checkout.delivery` | `/checkout/delivery` | `checkout.shipping_options` | Select an option returned for the current cart |
| `checkout.payment` | `/checkout/payment` | `checkout.payment_method` | Select and initialize the configured `pp_system` provider |
| `checkout.review` | `/checkout/review` | `checkout.order_review` | Refresh totals and explicitly approve order placement |
| `orders.confirmation` | `/orders/{confirmation_handle}/confirmation` | `orders.confirmation` | Show the real order returned by Medusa |

Secondary frame, detail, status, review, error, and diagnostic surfaces are composed from RouteDeck primitives. Medusa supplies their product-specific components and props.

### Product Operations And Transitions

| Operation | Declaring feature | Transition behavior after typed success |
| --- | --- | --- |
| `catalog.list` | catalog | `buyer.home` to `catalog.browse`, or refresh browse in place |
| `catalog.search` | catalog | remain on `catalog.browse` with an updated real result set |
| `catalog.open_product` | catalog | `catalog.browse` to `catalog.product` |
| `catalog.select_variant` | catalog | remain on `catalog.product` with a validated variant binding |
| `cart.create` | cart | remain on the current node and record one real Medusa cart |
| `cart.add_item` | cart | remain on `catalog.product` and observe the updated cart |
| `cart.open` | cart | product or browse context to `cart.summary` |
| `cart.update_item` | cart | remain on `cart.summary` and observe updated quantities and totals |
| `cart.remove_item` | cart | remain on `cart.summary` and observe the updated cart |
| `checkout.start` | checkout | `cart.summary` to `checkout.contact` |
| `checkout.save_contact` | checkout | `checkout.contact` to `checkout.delivery` |
| `checkout.select_shipping` | checkout | `checkout.delivery` to `checkout.payment` |
| `checkout.select_payment` | checkout | `checkout.payment` to `checkout.review` |
| `checkout.place_order` | checkout | `checkout.review` to `orders.confirmation` only after review approval and a real order result |
| `catalog.continue_shopping` | orders/catalog composition | `orders.confirmation` to `catalog.browse` |

`cart.create` is a declared, journaled new-session initialization operation bound by the cart feature. It uses required typed buyer-market configuration. It may be proposed again only after a `not_sent` failure. A `possibly_sent` attempt or unjournaled response becomes `external_outcome_unknown` and must not create another cart without explicit reconciliation or an explicit new session. `cart.add_item` requires an existing real cart and never creates one implicitly. Region, country/currency, sales-channel, publishable-key, and market context come from injected typed configuration or observed Medusa facts; they are not scattered constants.

Back, forward, cancel, deep-link entry, surface switching, and review accept or reject are RouteDeck interactions rather than commerce tools. They use the same navgraph and state transition engine, including dirty-state and recovery policies.

The ordinary happy path is:

```text
buyer.home
  -> catalog.browse
  -> catalog.product
  -> cart.summary
  -> checkout.contact
  -> checkout.delivery
  -> checkout.payment
  -> checkout.review
  -> orders.confirmation
```

### Context Providers

Entering or refreshing a node invokes the typed providers declared by that node:

- browse loads real products and prices
- product detail resolves its product handle, variants, prices, and inventory facts
- delivery loads shipping options for the current real cart
- payment loads configured payment providers for the current region and cart
- review refreshes the cart, addresses, selected delivery and payment facts, and totals
- confirmation loads or verifies the just-created order referenced by the successful completion result

Providers do not choose recovery behavior. Missing data, invalid references, transport failures, or Medusa errors produce explicit typed failures and visible RouteDeck state.

Navigation-only operations do not call product APIs; their destination provider performs the read exactly once. When an external operation already returns the complete authoritative observation needed by its destination, RouteDeck applies that observation without immediately repeating the same provider read. Providers run on direct entry, reload, explicit refresh, or a declared authoritative precondition refresh.

### RouteDeck Session State

RouteDeck retains the interaction state required to supervise the flow:

- session identity; schema, navgraph, session, and projection versions; and event cursor
- current node, bound route parameters, navigation history, and navigation policies
- current product and variant references
- operation-scoped allowlists of real product, variant, line-item, shipping-option, payment-provider, cart, and order identifiers
- current cart reference and observed checkout-completion flags
- sensitive form draft state and its public-projection redaction rules
- selected shipping and payment references
- typed buyer-market configuration and observed region, currency, country, and sales-channel facts
- pending `checkout.place_order` proposal and review state
- trusted, typed tool-result observations
- active surfaces, needs-input details, status, and visible failures

The public projection exposes display-safe product facts and opaque interaction handles. It never exposes private Medusa identifiers or sensitive form values. Private forms exclusively use the authenticated private-form channel defined below.

### Unified UI And Agent Operation Boundary

Product surface events and structured agent tool calls converge on the same declared operation. Both are supervised against the current RouteDeck state, legal operations, entity bindings, guards, input schema, and review policy. The frontend never calls Medusa directly, and a UI action cannot bypass a rule applied to the agent.

`checkout.place_order` is always a reviewed operation:

1. the UI or agent proposes the typed operation
2. RouteDeck validates the node, cart, inputs, bindings, guards, and refreshed review facts
3. RouteDeck records a pending review and projects the order-review surface
4. the user accepts or rejects through RouteDeck's internal review interaction
5. after acceptance, `RouteDeckOperationRunner` invokes the bound `complete_cart` handler once through the injected executor
6. RouteDeck observes the typed real order result or an explicit failure
7. only a verified real order result permits transition to `orders.confirmation`

A rejected review stays on `checkout.review`. A failed completion also stays on review with a visible error and does not synthesize an order or confirmation state.

## Developer-Experience And Failure Rules

- No subclassing a large product/runtime base class.
- Product handlers are ordinary typed functions.
- Product operation specifications and runtime handler bindings are separate but declared together in feature modules.
- Each product operation is declared once and drives supervision, context, LangGraph tool schema, surfaces, and frontend contracts.
- Public RouteDeck exports are small and intentional.
- Configuration is typed and injected.
- Features do not reach into other features' internals.
- Backend and frontend do not maintain duplicate catalogs.
- Route templates are compiled by RouteDeck; product code does not parse routes with regex.
- User intent is expressed through structured model tool calls, never keyword tables, regex matching, or phrase heuristics.
- Runtime behavior uses typed outcomes and declared transitions, not hardcoded action-target tables.
- Missing data, configuration, API access, handlers, providers, guards, or invariants fail loudly.
- Runtime product paths contain no embedded fixtures, synthetic fallback catalog, canned assistant output, heuristic substitute, or silent fallback. Versioned deterministic data is permitted only in explicitly labeled demo seed/reset infrastructure and isolated tests.
- Test doubles are isolated and explicitly named under test code.

## Persistence And Session Contract

### Durable Authority

`routedeck_core` defines a transactional `RouteDeckSessionStore` port. The standalone release supplies `routedeck_sqlite` as a reusable reference adapter rather than putting generic persistence inside the Medusa application.

The store persists:

- the canonical private RouteDeck session snapshot
- finalized conversation turns and typed tool observations in framework-neutral form
- session, projection, schema, and navgraph versions
- a bounded public event log for replay
- an append-only operation journal and allowlisted structured execution evidence
- encrypted checkout drafts and conversation content
- private cart, order, entity-binding, and review references

This is snapshot-plus-event-log persistence, not full event sourcing. Each accepted state mutation atomically updates the canonical snapshot and appends the corresponding public outbox events. The event table is the source for SSE replay; an in-process notifier may wake waiting streams but is never the durable source of truth.

The reference SQLite adapter runs in WAL mode and supports one application worker. Configuration that attempts multiple workers fails startup. Horizontal or multi-worker deployment is outside v1 and requires a different `RouteDeckSessionStore` adapter; it must not be simulated with in-memory coordination.

The adapter enforces that limit with a database-backed application-instance lease acquired through an atomic SQLite write; a second live RouteDeck process fails startup. The lease has an explicit heartbeat, stale-owner policy, and monotonically increasing fencing token checked by every state write and execution claim so an old paused process cannot resume after replacement. Write paths use short `BEGIN IMMEDIATE` transactions, compare-and-swap predicates, persisted execution claims, a typed `busy_timeout` setting with a five-second standalone default, and bounded cleanup batches. Concurrent browser tabs, SSE readers, and cleanup never bypass the session lease or mutation CAS rules.

The shipped application does not use LangGraph `InMemorySaver` or another independent state authority. Each LangGraph turn is request-scoped and is reconstructed from RouteDeck-owned conversation and tool history. An eventual resumable LangGraph checkpointer must adapt to the RouteDeck store rather than owning a competing session record.

### Versioning, Concurrency, And Request Identity

RouteDeck maintains three distinct monotonic values:

- `session_version`: compare-and-swap revision for canonical private state
- `projection_version`: revision that changes only when frontend-visible projection changes
- `event_cursor`: sequence assigned to every durable SSE event

Every mutation supplies an expected session version, a globally unique request ID, the declared operation, and typed arguments. Exactly one state-changing turn or operation may execute for a session at a time; snapshots, inspection, and SSE reads remain available.

- a version mismatch returns `version_conflict` and never retries the mutation
- a repeated request ID with the same canonical fingerprint returns its recorded pending or completed attempt without re-execution
- the same request ID with different input returns `request_id_reused`
- a conflicting active attempt returns `operation_in_progress`

Idempotency lookup occurs before stale-version rejection so a client can safely recover the already-recorded result of its own request.

A chat turn acquires one session execution lease. Its structured tool attempts are child attempts under that lease and do not acquire competing session claims. Product tool calls within a turn execute serially; parallel write attempts are rejected. Staging a review ends and releases the turn before waiting for the user. Review approval is a new request and lease that resumes the recorded attempt. Direct UI operations use the same lease mechanism.

### Guest Session And Deep-Link Identity

A guest session uses a cryptographically random opaque token stored in an `HttpOnly`, `SameSite=Lax` cookie. Session IDs are not placed in browser storage or URLs. First use explicitly creates a session; an expired known session returns `session_expired`, and starting another session is an explicit user operation.

Shareable routes may contain spec-declared public route keys such as a validated product handle; session-bound routes use opaque RouteDeck capability handles. Neither category contains private Medusa cart IDs, order IDs, line-item IDs, addresses, payment values, or operation arguments.

Shareable deep links are limited to `buyer.home`, `catalog.browse`, and `catalog.product`; product links use validated public product handles. Cart, checkout, review, and confirmation URLs are session-bound resume links that require the same guest cookie and valid RouteDeck capability bindings. Missing, expired, or cross-session bindings fail explicitly and never create replacement state.

### SSE Bootstrap And Reconnect

The frontend synchronizes deterministically:

1. fetch the canonical projection snapshot and its event cursor
2. connect to the session event stream after that cursor
3. replay every later durable event before following live events

SSE frames contain an event cursor, type, session version, optional projection version, and an allowlisted public payload. Browser reconnect uses `Last-Event-ID`, and the frontend reducer ignores duplicate cursors. A detected cursor gap puts the store into `resync_required` and performs the declared snapshot-resynchronization protocol without replaying any product operation. If the cursor is outside retention, the server emits `stream_reset_required` and closes the stream. Heartbeats are cursor-free SSE comments.

### Sensitive State

Checkout email and address values are collected through a RouteDeck private form surface and stored in a separately classified encrypted blob. The SQLite adapter requires an injected encryption codec and runtime key; missing encryption configuration fails startup without a plaintext fallback.

Sensitive classification is declared by schema rather than regex. Structured checkout values never enter the public projection, ordinary SSE payloads, model context, URLs, diagnostics, logs, traces, or exception messages. A session-authenticated, `Cache-Control: no-store` private-form channel may hydrate RouteDeck React form state in memory. The supported checkout flow does not ask the model to handle address fields. RouteDeck does not claim heuristic PII detection for arbitrary text a user independently types into chat.

The `pp_system` flow collects no card data. Real payment credentials, third-party payment callbacks, and PCI handling are outside v1.

### Restart, Retention, And Cleanup

On a normal process restart, committed navigation, history, conversation, private drafts, cart/order references, and pending review state resume. An in-flight model turn becomes `turn_interrupted`; partial assistant output is not treated as a completed turn. A write with a durable typed result is re-applied without invoking its handler, a write proven `not_sent` is interrupted and may be explicitly proposed again, and a sent write without a durable typed result becomes `external_outcome_unknown`. No write is automatically re-executed.

Medusa remains authoritative after restart. Context refresh and pre-operation checks re-read real cart or order facts. A missing cart produces an explicit `cart_missing` recovery state rather than silently creating a new cart. Successful order placement replaces the active cart reference with the returned order reference and purges the private checkout draft. RouteDeck cleanup never deletes Medusa carts or orders.

Retention values are typed configuration. The standalone defaults are:

- unfinished session: 24-hour idle TTL and seven-day absolute TTL
- completed session: 24 hours after confirmation
- event replay: 24 hours or 1,000 events per session, whichever is reached first
- operation journal: retained until its session is deleted
- cleanup: startup and every 15 minutes

Expiration hard-deletes RouteDeck state, private blobs, conversation, events, and operation evidence. A demo reset explicitly resets both Medusa demo data and RouteDeck sessions. A stored schema or navgraph version that cannot be migrated produces `session_upgrade_required`; it never silently resets or guesses a migration.

## Failure And Execution Semantics

### Typed Failures

Failures cross framework boundaries as a discriminated `RouteDeckFailure` containing a kind, stable code, phase, operation and request IDs, public message, recovery directive, and allowlisted safe details. Private diagnostics retain only explicitly allowlisted structured fields and provider metadata. Raw exception text, exception chains, response bodies, and request bodies are never persisted because they may contain sensitive data. Public projections never include stack traces, secrets, private Medusa IDs, address values, or payment data.

Failure kinds are:

- `contract`: invalid input, undeclared operation or outcome, missing binding, or invalid entity reference
- `state_conflict`: stale state, concurrent dispatch, or request-identity mismatch
- `context_provider`: a declared provider is unavailable or failed
- `guard`: expected denial or an infrastructure failure while evaluating a guard
- `review`: expired, stale, mismatched, or already-resolved review
- `transport`: connection, timeout, HTTP, or upstream availability failure
- `provider_protocol`: a response violates the typed Medusa client contract
- `business`: authoritative Medusa rejection involving inventory, cart, shipping, payment, or checkout
- `persistence`: a pre-send claim/store failure or failure to apply an already-durable result, commit state, or append outbox events
- `external_outcome_unknown`: a write may have succeeded but no authoritative result was captured
- `internal`: a violated framework invariant or unexpected executor failure

Medusa failures are classified from HTTP status and structured response fields only. Product code never parses messages with regex or heuristics to choose behavior.

### Operation Lifecycle

```text
received
  -> idempotency lookup
  -> version, input, entity, and context validation
  -> guards
  -> review staged or execution claimed
  -> product handler called
  -> typed execution result journaled
  -> declared outcome and transition applied
  -> state, projection, and public outbox committed
  -> operation completed
```

Guards and review always occur before the external side-effect boundary. A review freezes the normalized arguments, operation-spec version, proposal fingerprint, projection version, and expiry. Approval never accepts replacement arguments from the client. Before executing approval, RouteDeck refreshes authoritative cart facts and re-runs guards; changed totals, inventory, shipping, or payment invalidates the review and requires a new proposal.

The external call occurs outside the database transaction. The execution claim is persisted first. After a validated response is received, its typed result is journaled before the separate state-application transaction. If state application then fails, recovery may apply the already-journaled result without calling the product handler again. State, projection version, public events, and the completed marker are committed together.

Any external write that was sent but whose typed result was not durably journaled is `external_outcome_unknown`, including failure to journal a response that was received. `persistence` applies before send, or after a durable execution result exists and can be safely re-applied. Success is never returned before state, projection, outbox, and completion status commit.

Persisted evidence distinguishes `tool_started`, `tool_succeeded`, `tool_failed`, `tool_outcome_unknown`, `execution_result_recorded`, `state_committed`, and the terminal operation status. Assistant prose is never evidence that an operation succeeded.

### Retry Policy

RouteDeck does not automatically retry product tools in v1.

- replaying the same request ID returns its stored attempt and is not re-execution
- a failure proven to have occurred before sending may expose an explicit retry after authoritative refresh
- a business rejection requires corrected input or state
- a write that crossed the send boundary is never retried automatically
- downstream idempotency keys are forwarded only when the downstream contract explicitly supports them
- SSE reconnect and projection resynchronization are transport recovery, not product-operation retry

The Medusa HTTP adapter reports a typed delivery phase for every request: `not_sent`, `possibly_sent`, or `response_received`. Only `not_sent` permits a write to be proposed again without reconciliation. Every failure that cannot prove the request stayed local is `possibly_sent`; delivery phase is never inferred from exception text.

For a write, `response_received` describes transport evidence only. If the body does not validate as a definitive typed success or business failure, the operation is still `external_outcome_unknown`. `provider_protocol` is terminal by itself only for reads or for failures proven not to have crossed a write boundary.

### Ambiguous Order Completion

`checkout.place_order` treats Medusa's structured complete-cart result as authoritative:

- `type: "order"` records the returned real order, then permits confirmation
- `type: "cart"` records the structured checkout failure and stays on review
- a write proven not to have been sent is a definitive transport failure and may be proposed again after refresh and review
- a timeout, disconnect, truncated response, process death during the call, or other uncertainty after sending becomes `external_outcome_unknown`

Unknown completion remains on `checkout.review`, opens a dedicated recovery surface, removes `checkout.place_order` from legal operations, preserves allowlisted correlation evidence, and tells the user not to submit again. It never infers success and never invokes complete-cart again.

Medusa may bind an explicit `checkout.reconcile_order` handler. RouteDeck owns only the generic recovery state and supervision. Reconciliation succeeds only when that handler obtains an actual Medusa order and RouteDeck independently re-reads and validates it against the recorded cart and attempt. An operator assertion or supplied order ID alone can never create confirmation. If deterministic authoritative lookup is unavailable, v1 remains visibly blocked and preserves the disabled placement state across restart.

### Failure Projection

The last committed projection remains visible after failure. A missing provider never becomes an empty catalog or default object. Public errors contain a stable code, correlation ID, affected capability, and only legal next actions. Context-provider failures mark dependent surfaces unavailable and disable dependent operations. Commerce surfaces do not optimistically commit cart or order state; they update from validated authoritative results.

## Test Matrix And Release Gates

All four gates are mandatory.

| Gate | Exact pass criteria |
| --- | --- |
| Framework correctness | Unit and conformance tests cover feature compilation, route round-trips, transitions and history, review, supervision, projection redaction, persistence, SQLite instance locking/CAS, SSE sequencing, and the frontend reducer/store. Invalid manifests are rejected. Python and TypeScript contracts generated from one compiled definition have zero schema drift. Version-controlled coverage configuration enumerates critical state, navigation, supervision, projection, persistence, and reducer module globs; each group independently achieves at least 85% branch coverage. Overall coverage is advisory. |
| Boundary and adapter integrity | Executable import rules prove `routedeck_core` imports no LangGraph, FastAPI, React, or Medusa code. An endpoint-template inventory proves Medusa Store paths and HTTP transport exist only in `medusa/client/http.py`; handlers depend on `MedusaStoreClient`; browser network tests assert zero direct `/store/*` requests; product-specific APIs do not hide under the generic RouteDeck router; agent and surface operations pass through the same runner; and scan allowlists report zero phrase routers, keyword maps, regex intent routing, private-ID bypasses, canned responses, or hidden fallbacks. `boundary-report.json` records dependency, AST, endpoint, and network checks plus an explicit architectural-review result for semantic rules such as absence of commerce behavior. |
| Real commerce source of truth | From a clean, explicitly labeled and protected demo database, the typed client uses actual Medusa Store APIs to browse products, create and mutate a cart, set guest contact/address data, select a returned shipping option, initialize exactly `pp_system`, and complete the cart. Review staging and rejection produce zero complete-cart calls; one valid approval produces exactly one. Success requires `type: "order"` plus an independent Store API re-read whose items, quantities, totals, email, shipping method, and payment-provider evidence match the confirmation. A final protected reset removes test-created records and restores the normalized seed fingerprint. |
| Browser, agent, and developer experience | Chromium completes the entire guest flow against real Medusa and separately proves shareable catalog deep links and session-bound cart/checkout/confirmation resume links, history, cancel, reload at cart/review/confirmation, durable session recovery, SSE replay, monotonic versions, duplicate-event handling, explicit gap resynchronization, session isolation, surfaces, and the inspector. A deterministic full-flow suite may use an explicitly test-only scripted tool model. A separate configured-real-model smoke is mandatory and asserts structured state changes rather than exact prose; release is blocked when real-model access is unavailable. Clean install/import, builds, type checks, quickstart, reset, feature-authoring example, LangGraph examples, and documented failures all work locally. |

Mandatory negative cases include missing configuration, unavailable or unauthorized Medusa, malformed responses, typed `not_sent` and `possibly_sent` fault injection, invalid routes, stale versions, raw entity-ID injection, duplicate dispatch, unavailable variants, empty carts, invalid contact data, absent shipping or `pp_system`, changed carts after review, review rejection, approval replay, `type: "cart"`, ambiguous order completion, unknown surfaces, event gaps, and restart during review, execution, or unknown outcome.

Unknown-completion tests assert zero second complete-cart calls, disabled placement before and after restart, a visible recovery surface, and no confirmation without a real independently re-read Medusa order. LangGraph crash-window tests cover failure after result journaling but before RouteDeck state application, and failure after state commit but before the assistant turn finalizes; both reconstruct from RouteDeck-owned history and make zero additional product-handler calls.

The browser may call the generic RouteDeck session, projection, event, and dispatch transport plus Medusa product-owned application APIs such as chat. It must never call Medusa Store APIs directly. No Medusa commerce endpoint or product business logic may be implemented inside the generic RouteDeck transport.

### Release Proof Bundle

Every release verification writes a sanitized bundle:

```text
artifacts/release/<utc-run-id>/
  RELEASE_SUMMARY.md
  gate-results.json
  environment.json
  commands.jsonl
  junit/
  coverage/
  contracts/
    compiled-navgraph.json
    frontend-contract.json
    schema-parity.json
    conformance-results.json
    boundary-report.json
  medusa/
    seed-before.json
    store-api-trace.ndjson
    order-proof.json
    seed-after-reset.json
  runtime/
    supervision-trace.ndjson
    sse-trace.ndjson
    persistence-restart.json
  browser/
    playwright-report/
    full-flow-trace.zip
    browse.png
    cart.png
    review-pending.png
    confirmation.png
    network-boundary.json
  docs/
    clean-install.txt
    quickstart-smoke.txt
```

Artifacts redact secrets, PII, and raw private Medusa IDs. Non-PII correlation uses stable run-local identifiers. When correlation across PII or private IDs is essential, the verifier writes per-run keyed HMAC tokens and excludes the key from the bundle; otherwise it records comparison booleans only. `environment.json` records `runtime_target: local`, exact service versions, ports, and smoke URLs.

The reset command operates only on a dedicated local demo Medusa database or container volume containing the expected versioned sentinel. It refuses every other environment. The normalized seed fingerprint uses a version-controlled field allowlist and sorted business keys for catalog products/variants, regions, sales channels, shipping options, and enabled payment providers; generated IDs, timestamps, carts, orders, and other volatile metadata are excluded. Reset passes only when test-created records are absent and the normalized seeded dataset matches the pre-run fingerprint. Reset tooling is release infrastructure and is never callable as a product data fallback.

Load testing, broad cross-browser coverage, production payment providers, authenticated buyers, admin flows, pixel-perfect snapshot gates, and formal accessibility or security certification are outside v1. Chromium desktop plus one narrow-viewport smoke is sufficient.

## Local Execution Policy

Implementation, databases, backend and frontend services, test stacks, browser automation, and release verification run locally on the Windows development machine. The implementation must not probe, select, or fall back to the Mac mini. A remote runtime may be used only after a later explicit user request changes this decision.

## Design Completion Status

The architecture, ownership, LangGraph interface, feature authoring model, package boundaries, buyer flow, persistence, failure semantics, test matrix, release gates, developer experience, and anti-hardcoding rules above are approved.

The inline placeholder, consistency, scope, ambiguity, privacy, concurrency, and release-gate review is complete. The specification has no unresolved placeholders or known contradictory ownership, persistence, retry, deep-link, or runtime requirements.

The sole remaining design gate is final user approval of this written specification. After that approval, the writing-plans workflow produces the executable implementation plan. Implementation begins only after that plan is approved for Goal Mode execution.
