# System Flow Index - RouteDeck

Last updated: 2026-07-20
Status: current implemented flow

This is the compact sequence index. Contract meaning lives in
`docs/route-deck-reference.md`; ownership and proof live in
`architecture/feature-coverage.md` and `architecture/code-map.md`.

## Authoring And Compilation

```text
product Feature modules
  -> complete Nodes with operations/providers/guards/surfaces/outgoing edges
  -> small Application composition root selects features + entry node
  -> compile_app validates names, routes, bindings, outcomes, reachability
  -> RouteDeck derives incoming adjacency + immutable node index
  -> RouteDeck derives frontend contract + test paths
  -> bind_app validates exact async product implementations
```

The product does not maintain a separate transition graph. RouteDeck does not
generate the product's LangGraph topology.

## Runtime Assembly

```text
compiled app + product binding/session/validation/graph callbacks
  -> explicit SQLAlchemy URL + encryption key
  -> open_sqlalchemy_routedeck_runtime
  -> one store + codec + application lease
  -> build_routedeck_runtime
  -> one operation runner
  -> navigation over that exact runner
  -> configured projector + optional generic agent driver
  -> one RouteDeckRuntime exposed to adapters
```

Failure closes opened resources and propagates. No alternate dependency is
selected.

## Browser Bootstrap

```text
capture current address-bar path and history entry
  -> load compiled frontend contract
  -> try current guest session
  -> if 404/410/409 and incoming route is shareable: create session once
  -> reconcile captured path through RouteDeck navigation
  -> commit confirmed projection to browser history with replace
  -> start event stream and load durable conversation
  -> if conversation is empty: Medusa requests one assistant-initiated greeting
  -> RouteDeck coordinator validates the stream and converges versions/history
  -> Medusa translates any framework failure into product greeting copy
  -> render product shell
```

Session-bound routes never auto-create replacement state. Outcome-unknown
session creation or navigation retains the exact request for explicit recovery.
Greeting policy/copy stays in Medusa; request/event/synchronization behavior is
owned once by `@routedeck/core`.

## User Conversation

```text
typed user message + request id + expected session version
  -> claim durable turn and publish interaction-active state
  -> reconstruct finalized conversation + scoped model context/legal tools
  -> product LangGraph streams through generic RouteDeck driver
  -> tool calls cross the one operation runner
  -> persist user/assistant/tool turns and terminal event
  -> publish projection/session versions and finish SSE
```

## Assistant-Initiated Conversation

```text
assistant trigger + request id + expected session version
  -> same turn lease/replay/interruption lifecycle
  -> product entry graph, without synthetic HumanMessage
  -> exactly one streamed non-tool assistant result
  -> persist assistant turn + terminal event
```

Tools or review output on this path are contract failures.

## Operation And Review

```text
session + expected version + request id + declared operation + arguments
  -> load session and claim request fingerprint
  -> populate declared providers and entity allowlists
  -> evaluate declared guards
  -> block | needs_input | stage review | claim execution
  -> allowed product handler executes once
  -> record delivery evidence and typed outcome/failure
  -> validate/apply effects and navigation outcome
  -> atomically commit session + journals + public events
  -> notify subscribers after persistence
```

Review acceptance rechecks current context before execution. An uncertain
external outcome exposes declared reconciliation; it is not replayed silently.
Accept/reject always receives the host-selected non-empty session ID; the
runner has no implicit default-session path.

## Navigation And History

```text
open_path | back | forward | cancel | restore_history_entry
  -> validate expected version and canonical path
  -> enforce shareable/session-bound policy and resume capability
  -> execute declared route-entry operation when present
  -> commit exact location + unique entry identity + retained surface state
  -> browser pushes/replaces only confirmed canonical URL
```

Browser `popstate` restores an exact server entry. It never guesses direction or
replays commerce actions.

## Projection, Events, And Browser State

```text
committed runtime mutation
  -> default-deny public projection
  -> ordered event persisted before fanout
  -> SSE replay after cursor or explicit reset
  -> strict TypeScript decode
  -> authoritative observable state
  -> product React surfaces + conversation + read-only Navgraph
```

Private IDs/form values and diagnostic-only data do not enter public event or
model channels.

## Session Selection

```text
HTTP request
  -> host-owned RouteDeckSessionSelector
  -> authenticate/authorize principal and opaque handle when applicable
  -> already-authorized internal session id
  -> RouteDeck store access
```

The local Medusa host explicitly installs `GuestCookieSessionSelector`: one
HTTP-only cookie selects one guest session, separate browser profiles are
isolated, and tabs in one profile share the session. A production consumer may
instead implement `(principal, opaque session handle) -> authorized session_id`.
RouteDeck supplies the seam but does not own users, tenants, session listing,
authentication, or authorization policy.

## Authorities

- Decisions: ADR-006, non-superseded ADR-005, ADR-004.
- Contracts: `docs/route-deck-reference.md`.
- Coverage: `architecture/feature-coverage.md`.
- Ownership: `architecture/code-map.md` and `architecture/components/`.
- Validation: `test_index/README.md`.
