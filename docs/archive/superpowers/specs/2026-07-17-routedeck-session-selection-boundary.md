# RouteDeck Session Selection Boundary

**Status:** Approved design; implementation of authenticated session selection is a separate clean-break slice.

## Definition

A **session** is one durable RouteDeck execution context: its conversation, navigation position, review state, operation journal, leases, and projections. A **user** is a consumer-owned authenticated principal who may be authorized to access zero, one, or many RouteDeck sessions.

RouteDeck stores and executes a selected session. It does not own user accounts, organizations, tenant membership, or the policy that decides which sessions a user may access.

## Boundary

```text
consumer authentication
    -> consumer user/session registry
    -> SessionResolver
    -> authorized RouteDeck session_id
    -> RouteDeck state, navigation, reviews, and operations
```

The consumer owns:

- user, organization, and tenant identity;
- session listing, naming, archival, and sharing policy;
- authorization from the authenticated principal to an opaque session handle;
- the active-session choice for each browser tab or device.

RouteDeck owns:

- the durable state of the selected `session_id`;
- conversation, navigation, reviews, leases, concurrency, and idempotency;
- session creation, loading, expiry, and deletion ports;
- explicit failure when a selected session is missing, expired, or unavailable.

The transport adapter owns an injectable `SessionResolver`. It receives the authenticated request context and an opaque consumer-facing session handle, authorizes that selection through the consumer, and returns one explicit internal `session_id` before any RouteDeck store access. RouteDeck must never trust a raw browser-supplied internal session ID.

## Current guest adapter

The Medusa reference app uses one HTTP-only `routedeck_guest` cookie as its guest session selector. Different browsers receive different cookies and therefore isolated sessions. Tabs in the same browser profile share the cookie and currently share one guest session. This is correct for the guest reference adapter, not a universal multi-session identity model.

## Authenticated consumers and multiple sessions

An authenticated consumer supplies its own resolver. The UI may keep a different opaque session handle in each tab, while the resolver maps `(principal, handle)` to an authorized RouteDeck `session_id`. The same user can therefore open multiple sessions concurrently without placing RouteDeck IDs in browser storage or URLs.

Authorization happens before RouteDeck persistence access. A handle owned by another user or tenant fails explicitly; it never creates replacement state and never falls back to a default session.

## Clean-break follow-up

The framework follow-up should introduce the resolver contract at the FastAPI boundary and remove `default_session_id` from runtime APIs. Every runtime operation must receive the resolved explicit `session_id`. That work is intentionally separate from the Medusa loading-shell and video-story cleanup so identity semantics cannot be hidden inside a UI change.
