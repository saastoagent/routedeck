# FastAPI Conversation And Transport

## Purpose

`routedeck_fastapi` exposes one product-neutral `/api/routedeck` plane derived
from a `RouteDeckRuntime`. It owns transport contracts and status mapping, not
product routes, authentication policy, graph topology, or tool behavior.

## Owner Files

- `routedeck_fastapi/router.py` and `routes/`
- `routedeck_fastapi/runtime.py`, `dependencies.py`, and `session_http.py`
- `routedeck_fastapi/conversation_{projection,replay,stream}.py`
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
- Every router receives a host-owned `RouteDeckSessionSelector`; RouteDeck
  validates its selected internal ID but does not authenticate users or choose
  between a consumer's sessions.
- Conversation triggers share turn identity, replay/collision, persistence,
  interruption, projection synchronization, and SSE cleanup.
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

## Session Selection Boundary

`RouteDeckSessionSelector` is the required transport seam. A production host
may resolve `(authenticated principal, opaque consumer session handle)` to one
already-authorized internal RouteDeck session ID. RouteDeck never trusts a raw
browser-supplied internal ID and never chooses a consumer's replacement policy.
When RouteDeck creates a session, it awaits the selector's request-aware
`attach_created_session(request, response, session_id)` hook. The host may use
that hook to atomically bind the new internal session to an authenticated
principal and opaque handle, or attach its explicit guest policy.

`GuestCookieSessionSelector` is an explicit reference adapter for guest mode.
Its `GuestCookieSettings` requires the cookie name, `secure` flag, and path;
there is no generic insecure default. The Medusa local HTTP stack deliberately
supplies `secure=False`, while browser origins and all other deployment policy
remain explicit host configuration. The framework seam is implemented;
principal-aware authentication, session listing, and authorization remain the
consumer's responsibility.

## Evidence

```powershell
python -m pytest tests/fastapi/test_transport_smoke.py tests/fastapi/test_conversation_turns.py -q
```

Update this document for endpoint, dependency derivation, cookie/resolver,
conversation, replay, cancellation, SSE, form, inspection, or response changes.
