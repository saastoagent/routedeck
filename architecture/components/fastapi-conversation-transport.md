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
- Conversation triggers share turn identity, replay/collision, persistence,
  interruption, projection synchronization, and SSE cleanup.
- Assistant initiation emits no synthetic user message and cannot execute tools
  or stage review.
- Mutation origin policy, guest-cookie selection, cache headers, and public-safe
  error mapping are explicit.
- Missing runtime, session, driver, or contract state fails visibly.

## Current Adapter Limitation

The shipped selector is guest-only: one HTTP-only cookie carries the internal
session ID. There is no principal-aware opaque multi-session resolver.
`GuestCookieSettings.secure` also defaults to `False`, and the Medusa local host
does not override it. This is valid only for the explicitly local HTTP
reference runtime. A deployed consumer must supply explicit cookie/origin
policy and authorize a consumer-facing session handle before returning an
internal session ID to RouteDeck.

## Evidence

```powershell
python -m pytest tests/fastapi -q
```

Update this document for endpoint, dependency derivation, cookie/resolver,
conversation, replay, cancellation, SSE, form, inspection, or response changes.
