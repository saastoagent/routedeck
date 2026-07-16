# RouteDeck-Medusa Full Duplication Audit

Date: 2026-07-16
Mode: source read-only; documentation-only audit deliverable
Repository: `D:\Dev\AI Projects\routedeck`
Runtime location: local Windows only

## Executive Verdict

RouteDeck and the Medusa reference consumer do **not** yet have total
separation.

The backend runtime boundary is substantially clean: RouteDeck constructs the
runtime, persistence, runner, navigation, generic conversation driver, and
FastAPI transport. Medusa supplies product configuration, graphs, commerce
bindings, Store API behavior, and product UI. The current schema-3 boundary
checker passes all eight checks with zero violations.

Two high-impact duplicate control paths remain outside that checker's proof:

1. **Agent-design duplication:** `ModelTurnPolicy` performs a separate LLM
   intent decision before the buyer agent makes its own tool/no-tool decision.
   This is the immediate source of the observed live failure. It is not a
   parallel-tool-call failure.
2. **Consumer architectural duplication:** the Medusa frontend manually
   consumes and validates the assistant-initiated SSE lifecycle even though
   RouteDeck already owns the generic conversation client, synchronization,
   and presentation lifecycle.

There is also one checkout-integrity duplicate: the contact fingerprint
algorithm is independently implemented in checkout and orders. Several
medium/low code-clone families remain, but they do not create competing runtime
state authorities.

No source fix is made by this audit. In particular, this report does **not**
recommend disabling parallel tool calls as a substitute for removing the
redundant intent classifier.

## Controlling Ownership

The audit uses the following authority chain:

1. [ADR-004](../decisions/ADR-004-routedeck-medusa-consumer-driven-runtime.md)
2. [ADR-005](../decisions/ADR-005-operation-centric-state-and-consumer-structure.md)
3. [ADR-006](../decisions/ADR-006-framework-owned-runtime-and-conversation-boundary.md)
4. [Runtime-boundary implementation plan](../docs/superpowers/plans/2026-07-15-routedeck-runtime-boundary-refactor.md)
5. Current source

The decisive rules are:

- RouteDeck owns canonical state, legal-operation exposure, supervision,
  generic runtime assembly, conversation lifecycle, transport, client
  synchronization, and reusable React presentation behavior.
- Medusa owns commerce declarations and implementations, Store API behavior,
  product graphs/prompts/models, product policy, product rendering, and product
  copy.
- A product may choose policy and graph topology, but it must not duplicate a
  decision already made by its buyer agent or a lifecycle already owned by a
  RouteDeck adapter.
- Defensive validation at a trust boundary is not automatically duplicate
  authority. It becomes a duplicate finding when two maintained implementations
  independently encode the same rule and can drift.

## Scope And Method

The maintained production-source inventory covered:

| Scope | Files | Lines |
| --- | ---: | ---: |
| RouteDeck Python packages | 137 | 20,241 |
| Medusa backend package | 82 | 11,297 |
| RouteDeck TypeScript/React packages | 73 | 9,858 |
| Medusa frontend production source | 33 | 4,435 |
| **Total** | **325** | **45,831** |

The audit combined:

- authority and dependency-direction review;
- production file and import inventory;
- exact SHA-256 whole-file comparison;
- Python AST function-body clone comparison, including a normalized structural
  pass;
- normalized TypeScript/TSX block comparison;
- manual tracing of runtime, agent, transport, persistence, frontend state,
  schemas, tests, release configuration, and documentation;
- the existing schema-3 boundary checker.

Excluded from maintained-source duplication counts were `.git`, `.venv`,
`node_modules`, generated `dist`, caches, recordings, release artifacts,
historical `codex_chats_and_memories`, and test result directories. Tests were
inspected as evidence of which architecture they enforce, but were not counted
as production source.

No broad unit, integration, browser, or E2E suite was run. The only executable
gate was the static boundary report:

```text
schema_version: 3
status: pass
violation_count: 0
checks: 8/8 pass
```

That pass is useful but incomplete: the current checker proves Python runtime
ownership and transport separation; it does not detect the agent intent
classifier or generic frontend assistant-stream control in product code.

## Finding Summary

| ID | Severity | Classification | Duplicate responsibility | Verdict |
| --- | --- | --- | --- | --- |
| DUP-01 | High | Agent design | User intent/tool-use decision | Remove duplicate layer |
| DUP-02 | High | Consumer architecture | Assistant-turn client lifecycle | Move to RouteDeck |
| DUP-03 | High | Product integrity | Contact fingerprint calculation | Consolidate immediately after DUP-01/02 |
| DUP-04 | Medium | Framework internal | Current-node resolution | Consolidate |
| DUP-05 | Medium | Product integration | Medusa failure/outcome translation | Consolidate explicit helpers |
| DUP-06 | Medium | Product contract | Surface schemas and frontend decoders | Generate or prove parity; share primitives |
| DUP-07 | Low | Framework internal | Awaitable provider resolution | Consolidate opportunistically |
| DUP-08 | Low | Product UI | Review/confirmation order rendering | Share product presentation primitives |
| DUP-09 | Low | Configuration | Identical package TypeScript configs | Optional consolidation |
| DUP-10 | Low | Stale product mirror | Unused frontend operation identifiers | Delete with next cleanup |

## Detailed Findings

### DUP-01 — A separate model decides intent before the buyer agent

Severity: **High**
Classification: **agent design**, not a RouteDeck runtime-boundary fault
Status: **confirmed and reproduced live**

There are two decision makers for the same question:

- RouteDeck injects the current context and only legal operations in
  [`routedeck_langgraph/middleware.py`](../routedeck_langgraph/middleware.py),
  lines 48-95. Its trusted intent policy tells the buyer model that legality is
  permission, not user intent, in
  [`routedeck_core/context/framework_policies.py`](../routedeck_core/context/framework_policies.py),
  lines 13-34.
- The buyer model is the natural owner of deciding whether the current request
  requires a tool call.
- Before that buyer model runs, [`turn_policy.py`](../examples/medusa-agent/backend/medusa_agent/turn_policy.py),
  lines 15-105, invokes a second structured-output model and removes all tools
  when it returns `conversation`.

The extra decision is wired through:

- [`agent.py`](../examples/medusa-agent/backend/medusa_agent/agent.py), lines
  39-66 and 81-92;
- [`runtime.py`](../examples/medusa-agent/backend/medusa_agent/runtime.py),
  lines 155-172, including ignored stream-event tags;
- [`config.py`](../examples/medusa-agent/backend/medusa_agent/config.py),
  including the third `OPENAI_TURN_POLICY_MODEL` role;
- Compose, demo provisioning, release evidence, scripted E2E support, backend
  integration tests, and the Medusa reference documentation.

The two paths can disagree:

- the classifier can hide tools even though the buyer agent would need one;
- the classifier can expose tools even though the buyer agent should answer
  conversationally;
- classifier failure prevents the buyer model from running at all;
- each normal buyer message pays for and waits on a second model call.

#### Live failure evidence

The exact human-flow diagnostic failed inside
`ModelTurnPolicy.decide(...)` before buyer-agent tool planning. The structured
classifier returned two concatenated JSON objects:

```text
{"mode":"action"}
{"mode":"action"}
```

Pydantic rejected the result as trailing characters. The prior catalog turn had
issued one `catalog.list` call. The failing darker-options turn did not reach
buyer-agent tool planning. Therefore that observed failure was **not** caused
by parallel variant lookup or parallel tool execution.

#### Correct ownership and recommendation

- Keep RouteDeck's default-deny context, legal-tool filtering, runner
  supervision, and typed tool results.
- Let the buyer model decide whether and which currently exposed tool to call.
- Remove `turn_policy.py`, the middleware parameter and composition, the third
  model role, ignored tag, release/config wiring, and tests that require tools
  to be hidden by a classifier.
- Replace the classifier-specific test with a product-agent test showing that a
  conversational response may complete without a tool call even when legal
  tools are available.
- Do not add `parallel_tool_calls=False` as the fix for this finding. Serial or
  parallel tool execution is a separate supervision decision.

### DUP-02 — Medusa reimplements the assistant-turn stream state machine

Severity: **High**
Classification: **RouteDeck/consumer architectural fault**
Status: **confirmed from source**

RouteDeck already owns:

- the typed assistant-turn endpoint and backend trigger;
- SSE decoding in `@routedeck/core`;
- request identity checks, event-to-presentation transitions, version
  synchronization, interruption handling, retry/discard behavior, and
  conversation presentation in
  [`useRouteDeckConversation.ts`](../packages/react/src/conversation/useRouteDeckConversation.ts),
  lines 45-175.

Medusa nevertheless owns a second generic stream consumer in
[`frontend/src/main.tsx`](../examples/medusa-agent/frontend/src/main.tsx), lines
110-207. It independently implements:

- request-ID validation;
- stream terminal-state validation;
- assistant completion/version capture;
- rejection of user/review events;
- conflict recovery;
- RouteDeck store synchronization;
- canonical conversation reload.

The same file also implements another random request-ID factory at lines
223-231 even though `@routedeck/core` exports `createRouteDeckRequestId()`.

This is more than product bootstrap choice. Medusa may decide **when** an empty
conversation should receive a greeting and may render product-specific error
copy, but the stream protocol and synchronization algorithm are reusable
RouteDeck behavior.

The two state machines already differ. The interactive hook owns abort,
outcome-unknown retention, retry/discard, and presentation actions; the startup
implementation has a separate error and conflict policy. Future event changes
can update one without the other.

Recommendation:

- add one headless RouteDeck assistant-initiation coordinator/helper in
  `@routedeck/core`, or extend the existing conversation coordinator with a
  typed assistant trigger;
- make it own request identity, terminal-state proof, synchronization, replay,
  cancellation, and final history reload;
- let Medusa call that helper when the canonical conversation is empty;
- use the framework request-ID factory;
- extend the executable boundary check to reject product-owned switches over
  RouteDeck assistant stream event types.

### DUP-03 — Checkout and orders independently hash the same contact facts

Severity: **High**
Classification: **product integrity duplication**
Status: **confirmed structural clone**

[`checkout/models.py`](../examples/medusa-agent/backend/medusa_agent/features/checkout/models.py),
lines 502-523, and
[`orders/models.py`](../examples/medusa-agent/backend/medusa_agent/features/orders/models.py),
lines 257-278, independently build and hash the same payload:

- email;
- shipping address JSON;
- billing address JSON;
- identical canonical JSON options;
- SHA-256 output.

This fingerprint crosses the cart-completion/order-verification boundary. If
one side adds normalization or a field and the other does not, a real completed
order can be rejected as unverifiable or a meaningful difference can be
missed.

Recommendation: create one product-owned canonical contact-fingerprint
function over an explicit normalized contact value, and use it for both cart
and order sources. Keep the function product-side; RouteDeck must not learn
Medusa contact semantics.

### DUP-04 — Current-node lookup is repeated across RouteDeck

Severity: **Medium**
Classification: **framework-internal code and invariant duplication**
Status: **confirmed; three byte-identical bodies plus two variants**

The same linear node lookup appears in:

- [`context/agent.py`](../routedeck_core/context/agent.py), lines 108-121;
- [`context/scope.py`](../routedeck_core/context/scope.py), lines 86-99;
- [`projection/projector.py`](../routedeck_core/projection/projector.py), lines
  262-275;
- [`navigation/engine.py`](../routedeck_core/navigation/engine.py), lines
  312-319;
- [`navigation/transactions.py`](../routedeck_core/navigation/transactions.py),
  lines 406-419;
- [`supervision/guards.py`](../routedeck_core/supervision/guards.py), lines
  372-377, where a missing node leaks `StopIteration` instead of a typed
  RouteDeck error.

The first three bodies are structurally and textually identical. The other
three encode the same lookup with different exceptions.

Recommendation: put one immutable node index/lookup on the compiled or bound
application. Keep caller-specific public error mapping at navigation/transport
boundaries, but do not repeat the lookup invariant.

### DUP-05 — Medusa failure translation and small operation helpers are cloned

Severity: **Medium**
Classification: **product integration duplication**
Status: **confirmed structural clone family**

The same Medusa failure-to-`RouteDeckFailure` construction exists in:

- cart `failure_outcome`, lines 204-227;
- checkout `operation_failure`, lines 111-134;
- orders `client_failure`, lines 210-233.

Cart and checkout also repeat protocol-failure wrappers. Other exact or
normalized clones include:

- `public_values(...)` in catalog, checkout, and orders;
- exact operation-argument validation in cart and checkout;
- current/reviewed cart extraction in checkout and orders.

The operation-specific phase and recovery meaning must remain explicit, but
the provider mapping, safe-details construction, and protocol boilerplate do
not need three maintained implementations.

Recommendation: introduce a small product-level integration helper with
explicit required arguments for phase, delivery phase, failure kind, effects,
and public message. Do not introduce a fallback or infer recovery behavior in
the helper.

### DUP-06 — Product surface contracts are maintained in backend schemas and frontend decoders

Severity: **Medium**
Classification: **contract mirror with drift risk**, not duplicate canonical
state
Status: **confirmed**

The backend declares authoritative JSON Schemas on `SurfaceSpec`, for example:

- catalog collection/product schemas in `features/catalog/feature.py`;
- cart summary schema in `features/cart/feature.py`;
- contact, shipping, payment, review, and recovery schemas in
  `features/checkout/feature.py`;
- confirmation schema in `features/orders/feature.py`.

Those schemas are exported in the RouteDeck frontend contract. The Medusa
frontend then manually restates the field sets, types, enums, lengths, and
required values in surface-local decoders such as:

- `decodeCatalogGrid`, `decodeProductDetail`, and `decodeCatalogVariant`;
- `decodeCartSummary` and `decodeCartLineItem`;
- `decodeContactProjection`, `decodeShippingProjection`,
  `decodePaymentProjection`, and `decodeOrderReview`;
- `decodeVerifiedOrder`.

Defensive browser validation is correct. The duplication is that validators are
hand-maintained independently of the already-delivered schema. Current frontend
test contracts commonly use `public_props_schema: {}`, so those tests do not
prove decoder/schema parity.

There is also repeated decoder infrastructure. `exactKeys` and `invalid`
families are separately implemented in catalog, cart, contact, shipping, and
payment modules.

Recommendation:

- keep backend `SurfaceSpec.public_props_schema` canonical;
- generate product TypeScript validators/types from the compiled product
  contract, or add one build-time parity gate that executes the server schemas
  against the same valid/invalid fixtures as the browser decoders;
- consolidate only the generic product decoder primitives into a product-level
  utility; keep surface-specific semantic checks near their components.

### DUP-07 — FastAPI resolves sync/async providers twice

Severity: **Low**
Classification: **framework internal utility duplication**
Status: **confirmed normalized clone**

`routedeck_fastapi/runtime.py::resolve_runtime` and
`routedeck_fastapi/session_http.py::resolve_dependencies` both call a provider,
await it when necessary, type-check the result, and raise the same unavailable
failure. Their result types differ, so no authority is duplicated, but the
control skeleton is repeated.

Recommendation: use one private generic `resolve_provider(...)` helper with an
explicit expected type and public error. This is opportunistic cleanup, not a
release blocker.

### DUP-08 — Order review and confirmation repeat buyer presentation

Severity: **Low**
Classification: **product UI duplication**
Status: **confirmed normalized TSX clone**

`OrderReviewSurface.tsx` and `OrderConfirmationSurface.tsx` repeat order line
rendering and the five subtotal/shipping/tax/discount/total rows. Their actions
and status copy are correctly different.

Recommendation: share product-owned order-line and order-total presentation
components while keeping proposal and confirmation actions separate.

### DUP-09 — React and testing package TypeScript configs are identical

Severity: **Low**
Classification: **exact whole-file configuration duplicate**
Status: **confirmed by SHA-256**

`packages/react/tsconfig.json` and `packages/testing/tsconfig.json` are the only
non-empty exact whole-file duplicate in the maintained scan.

This has no runtime impact. Consolidate into a package-level base config only if
another package needs the same settings; otherwise the small explicit configs
are acceptable.

### DUP-10 — The frontend keeps unused copies of backend operation IDs

Severity: **Low**
Classification: **stale contract mirror**
Status: **confirmed unused production export**

`frontend/src/routedeck/identifiers.ts` defines `MedusaOperationType` with
`catalog.list` and `cart.open`, but no frontend production caller uses it.
Surface components correctly resolve declared affordances instead of calling
operation IDs directly.

Recommendation: delete the unused operation constant. Keep only identifiers
that the product UI truly needs, or generate them from the product contract.

## Intentional Similarities That Are Not Duplicate Authorities

The following were inspected and should not be collapsed merely because names
or shapes are similar:

| Similar paths | Why they are separate |
| --- | --- |
| `routedeck_core/contracts/session.py` and `state/session.py` | Immutable contracts versus state construction/current-session invariants. |
| SQLAlchemy `sessions.py`, `turns.py`, `operations.py` and `store_parts/*` | Repositories own ORM operations; transaction services own async/lifecycle boundaries; `SqlAlchemySessionStore` is the sole public facade. |
| `routedeck_fastapi/private_forms.py` and `routes/private_forms.py` | Private-form domain/serialization services versus endpoint registration. |
| Backend validation and frontend route validation | The server is canonical; browser validation is a non-authoritative UX/security boundary. |
| `RouteDeckObservableState` and React conversation presentation state | Canonical session/projection mirror versus ephemeral rendered messages/stream status. ADR-006 explicitly permits this split. |
| `RouteDeckMiddleware` legal-tool filtering and runner/store guards | Exposure, execution authorization, and durable concurrency are distinct defense layers. |
| No-tool assistant-entry graph and framework rejection of entry tool calls | Product graph configuration plus framework contract validation. |
| Python contracts, generated TypeScript types, and strict runtime decoders | Generated compile-time representation plus runtime trust-boundary validation; parity must remain tested. |
| `routedeck_testing`, `packages/testing`, and E2E scripted support | Language-specific, explicitly test-only infrastructure. No scripted model is imported by the live product path. |
| Product feature `bindings.py`, `feature.py`, `providers.py`, and operation modules | Declaration, dependency wiring, context resolution, and side effects are distinct vertical-slice roles. |

## Parallel Tool Calls: Adjacent Finding, Not The Fix

The source currently has two relevant facts:

- the live buyer `ChatOpenAI` constructor in `agent.py`, lines 105-111, does
  **not** pass a provider option disabling parallel tool calls;
- the generic driver rejects any model response containing more than one tool
  call in `routedeck_langgraph/agent_driver.py`, lines 125-137.

Therefore the reference document's sentence “Parallel tool calls are disabled
and rejected” is only half-supported by current code: they are rejected by the
driver, not disabled at model construction.

The accepted design says product tool calls execute serially. Whether RouteDeck
should continue rejecting multi-call batches, serialize safe reads, or model
read/write concurrency explicitly is a separate architecture decision. It must
not be used to explain or patch the observed classifier JSON failure.

## Boundary Checker Blind Spots

The current boundary checker correctly proves:

- no reverse Medusa imports in RouteDeck core;
- Store endpoint and HTTP-client ownership;
- typed Medusa client-port usage;
- no browser-to-Medusa Store calls;
- product transport separation;
- one framework-built runtime/runner/navigation path;
- no product `astream_events(...)` loop;
- no obvious fixture/regex/canned fallback policy path.

It does not currently prove:

- that a product graph has only one intent/tool-use decision maker;
- that product frontend code does not implement the RouteDeck assistant SSE
  state machine;
- parity between product surface JSON Schemas and product UI decoders;
- uniqueness of product-integrity algorithms such as order verification
  fingerprints.

The checker can therefore remain green while DUP-01, DUP-02, DUP-03, and DUP-06
exist.

## Recommended Order Of Work

This is an audit recommendation only; no implementation is authorized by this
report.

1. Remove the turn-policy classifier and all fan-out. Target only the buyer
   agent middleware/config tests and immediate live chat behavior. Do not alter
   parallel-tool supervision in this change.
2. Move the assistant-initiation stream coordinator and request-ID generation
   into RouteDeck. Target core conversation reliability and the initial-greeting
   bootstrap flow.
3. Consolidate the contact fingerprint and test cart-versus-order equivalence
   against real typed Medusa values.
4. Add the compiled-app node index/resolver and migrate the six lookup sites.
5. Consolidate Medusa failure/decoder primitives without hiding feature-specific
   phases or recovery semantics.
6. Add surface-schema/decoder parity generation or a focused executable parity
   gate.
7. Clean the low-risk UI/config/dead-identifier duplicates.
8. After targeted slice checks, run the already-planned human-like real-Medusa
   checkout recording once as the final gate.

## Workspace Residue

Two old-looking root paths were inspected:

- `react/` is empty.
- `routedeck_sqlite/` contains only ignored `__pycache__/*.pyc` files from the
  retired adapter; it contains no maintained Python source.

They are local residue, not competing product implementations. Generated
`dist/` output and caches are similarly outside maintained source. Cleanup is
optional and was not performed.

## Final Answer To The Architectural Question

- **Has the backend RouteDeck/Medusa runtime boundary been separated?** Largely
  yes, and the current executable backend checks support that claim.
- **Has all duplicate authority/control been removed?** No.
- **What caused the live darker-options failure?** The duplicate Medusa
  turn-policy classifier: an agent-design fault.
- **Is there still a RouteDeck/consumer architectural duplication?** Yes: the
  Medusa frontend owns a generic assistant-turn stream lifecycle that belongs in
  RouteDeck.
- **Are parallel tool calls the cause or the fix?** Neither for the reproduced
  failure. Keep that decision separate.
