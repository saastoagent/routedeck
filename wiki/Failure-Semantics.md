# Failure Semantics

RouteDeck treats failure semantics as part of the public contract. Required
dependencies fail visibly; they do not silently switch to substitutes.

## Fail closed

RouteDeck does not replace a missing or failed dependency with:

- an in-memory store;
- another model or provider;
- cached or synthetic data;
- an empty object that looks successful;
- a fixture or scripted response;
- a heuristic route;
- an implicit default session;
- a generic success message.

Optional behavior must be explicit in the contract or caller choice.

## Public failure shape

Public failures contain a stable kind/code/phase, correlation ID, and safe
message. Raw exceptions, response bodies, internal IDs, credentials, and
private-form values remain server-side.

## Confirmed rejection versus unknown outcome

| Evidence | Interpretation | Client behavior |
| --- | --- | --- |
| Received typed `4xx` contract/conflict response | Confirmed rejection | Show error; do not retry as if delivery were unknown |
| Valid success envelope | Confirmed server result | Converge to committed versions |
| `5xx` after a mutation may have reached the server | Outcome may be unknown | Retain exact request and payload |
| Lost response or malformed success envelope | Outcome may be unknown | Retain exact request and payload |
| SSE disconnect | Transport interruption | Reconnect from last cursor |
| Session `404` or `410` | Terminal missing/expired session | Stop stream and expose error |

## External-write uncertainty

For side effects outside the RouteDeck transaction, the handler reports
delivery evidence. `possibly_sent` becomes explicit
`external_outcome_unknown`. The product must provide an independent
reconciliation path. Repeating the original write with a new ID would be
unsafe and is not automatic.

## Version and identity conflicts

- A stale expected session version fails before executing product behavior.
- An identical request ID and input replays the recorded result.
- The same ID with different input fails as `request_id_reused`.
- A stale review proposal is rechecked and rejected.
- A stale opaque handle fails before the handler receives a private ID.
- A non-owner or expired lease cannot commit over the current owner.

## Conversation interruption

Graph failure records an interrupted turn before the public terminal event. If
that write cannot be proven, RouteDeck reports outcome-unknown rather than
pretending the turn ended cleanly.

## Recovery principle

Recovery is an explicit, named layer:

```text
primary operation fails or becomes uncertain
  -> RouteDeck records typed evidence
  -> public projection exposes approved recovery posture
  -> user or product explicitly invokes reconciliation
  -> product checks its independent source of truth
  -> RouteDeck commits the recovered state
```

This makes the difficult case observable and prevents retry logic from being
smuggled into unrelated functions.
