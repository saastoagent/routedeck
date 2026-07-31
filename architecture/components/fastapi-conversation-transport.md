# FastAPI Conversation And Transport

## Purpose

`routedeck_fastapi` exposes one product-neutral `/api/routedeck` plane derived
from a `RouteDeckRuntime`. It owns transport contracts and status mapping, not
product routes, authentication policy, graph topology, or tool behavior.

## Owner Files

- `routedeck_fastapi/router.py` and `routes/`
- `routedeck_fastapi/runtime.py`, `dependencies.py`, and `session_http.py`
- `routedeck_fastapi/conversation_{projection,replay,sse,stream}.py`
- `routedeck_fastapi/{contracts,responses,sse,security}.py`
- `routedeck_fastapi/{private_forms,inspection}.py`

## Route Groups

- compiled frontend contract;
- session creation/current projection;
- dispatch, review, and navigation;
- user chat and assistant-initiated conversation;
- ordered event SSE and inspection;
- authorized private-form read/write.

## Invariants

- `create_routedeck_router_from_runtime_provider(...)` is the one public router
  composition path.
- Every request resolves dependencies from one runtime; products do not build a
  second dependency bundle.
- `POST /sessions` delegates creation, durable replay/collision handling,
  product initialization, and declared entry-run attachment to
  `RouteDeckRuntime.provision_session(...)`. The adapter only validates the
  request, creates the HTTP response, projects the returned current snapshot,
  and invokes host attachment.
- The adapter-facing `SessionProvisioner` protocol exposes only the runtime's
  exact keyword-only `session_id`/`request_id` call shape; it is not an
  unrestricted callable seam.
- Every router receives a host-owned `RouteDeckSessionSelector`; RouteDeck
  validates its selected internal ID but does not authenticate users or choose
  between a consumer's sessions.
- Conversation triggers share turn identity, replay/collision, persistence,
  interruption, projection synchronization, and SSE cleanup.
- Public conversation history and every retained compatibility chat SSE
  payload are serialized through frozen, extra-forbid Pydantic transport
  models. Those same models are included in the generated schema catalog used
  by the TypeScript decoders; no handwritten wire-field list is authoritative.
  Legacy event request IDs contain 1 to 256 Unicode code points, and public version
  integers remain within JavaScript's non-negative safe-integer domain.
  Public history preserves the canonical turn contract: turn IDs are non-empty,
  while a present request ID has no stronger constraint than the canonical
  `ConversationTurn` model.
- The runtime owns one process-local conversation-run coordinator. Subscribers
  may disconnect and later attach by request ID and cursor without cancelling
  user-message or assistant-initiated execution; terminal truth remains the
  existing durable mutation, conversation, and session state.
- A start response is returned only after `begin_turn(...)` durably claims the
  lease and publishes the active interaction request ID. Detached execution
  receives that existing lease; there is no accepted non-durable run window.
- Run progress is transient and accumulated. The coordinator retains only the
  latest snapshot, so a subscriber may observe a cursor jump but never a
  regression. Durable terminals are evicted and reconstructed from mutation
  truth with a max-safe terminal cursor. RouteDeck adds no durable run table,
  renewable lease, or recovery worker.
- Conversation fingerprints are domain-separated as
  `rdconv1:<run-kind>:<hash>`. This preserves interrupted user-run kind across
  restart without storing the private user message in mutation metadata.
- An active public interaction includes the run request ID so a browser can
  discover and attach to a server-started declared entry turn.
- Assistant initiation emits no synthetic user message and cannot execute tools
  or stage review.
- Mutation origin policy, session selection, cache headers, and public-safe
  error mapping are explicit.
- An expired session-bound resume capability is a terminal HTTP 410 bootstrap
  condition, allowing the framework client to offer its legal new-session
  recovery instead of retrying an internal-error response.
- Every non-streaming conversation error uses the canonical `RouteDeckFailure`
  envelope; conversation routes do not define a second compact error shape.
- Missing runtime, session, driver, or contract state fails visibly.
- Authenticated inspection includes an optional driver-owned `agent_context`.
  The LangGraph adapter populates it only when the product explicitly declares
  its inspection system prompt; otherwise the field is `null`. The payload is
  derived from the same canonical snapshot and default-deny model-context
  builder used for model calls, and remains private/no-store.
- A non-durable interruption is never cached or emitted as terminal. If
  interruption persistence fails, run reads fail visibly; if the commit
  succeeded before a later response-path failure, the next read reconstructs
  the durable mutation.

The run plane is `POST /conversation/runs`,
`GET /conversation/runs/{request_id}`, and
`GET /conversation/runs/{request_id}/events?after={cursor}`. Legacy chat and
assistant-turn endpoints delegate to this detached coordinator.

## Session Selection Boundary

`RouteDeckSessionSelector` is the required transport seam. A production host
may resolve `(authenticated principal, opaque consumer session handle)` to one
already-authorized internal RouteDeck session ID. RouteDeck never trusts a raw
browser-supplied internal ID and never chooses a consumer's replacement policy.
When RouteDeck creates a session, it awaits the selector's request-aware
`attach_created_session(request, response, session_id)` hook. The host may use
that hook to atomically bind the new internal session to an authenticated
principal and opaque handle, or attach its explicit guest policy.
Exact create replay attaches the session returned by the runtime provisioner,
not a newly generated candidate ID.

`GuestCookieSessionSelector` is an explicit reference adapter for guest mode.
Its `GuestCookieSettings` requires the cookie name, `secure` flag, and path;
there is no generic insecure default. The Medusa local HTTP stack deliberately
supplies `secure=False`, while browser origins and all other deployment policy
remain explicit host configuration. The framework seam is implemented;
principal-aware authentication, session listing, and authorization remain the
consumer's responsibility.

## Evidence

```powershell
python -m pytest tests/fastapi/test_transport_smoke.py tests/fastapi/test_conversation_turns.py tests/fastapi/test_public_response_models.py tests/fastapi/test_session_provisioner_typing.py -q
pnpm contracts:check
pnpm --dir packages/core exec vitest run --config vitest.config.ts src/conversation/codec.test.ts
```

Update this document for endpoint, dependency derivation, cookie/resolver,
conversation, replay, cancellation, SSE, form, inspection, or response changes.
