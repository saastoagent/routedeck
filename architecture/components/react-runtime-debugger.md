# Headless And React Runtime

Authority: ADR-006 for runtime ownership; ADR-005 remains active where ADR-006
does not supersede it.

## Purpose

`@routedeck/core` owns strict browser contracts, clients, and canonical
observable RouteDeck state. `@routedeck/react` owns product-neutral bindings,
named conversation presentation actions, and UI primitives.
`@routedeck/testing` remains test-only.

## Owner Files

- `packages/core/src/contracts/{decode,json,projection,events,operations,frontend,privateForms,inspection}.ts`
- `packages/core/src/conversation/{types,codec,client}.ts`
- `packages/core/src/store/{store,bootstrap,synchronization,operations,lifecycle}.ts`
- `packages/core/src/{client,routing,private-forms}/*`
- `packages/react/src/conversation/{presentation,useRouteDeckConversation}.ts`
- `packages/react/src/{provider,hooks,surfaces,navigation,private-forms,review,status,inspector}/*`
- `packages/testing/src/*`

## Public Interfaces

- `createRouteDeckAgentClient(...)` loads canonical conversation, streams user
  chat, and streams typed assistant initiation through
  `streamAssistantTurn(...)`.
- `createRouteDeckStore(...)` remains the public coordinator facade; focused
  bootstrap, synchronization, operation, and lifecycle coordinators are
  internal.
- `RouteDeckObservableState` and named store actions/selectors remain the
  canonical browser view of session/projection state.
- `ConversationPresentationActions` exposes named methods such as
  `beginTurn`, `restoreSnapshot`, `showUserMessage`, `appendAssistantText`,
  `finalizeAssistant`, `requireReview`, `completeTurn`, and `failTurn`.
- `useRouteDeckConversation(...)` owns abort, SSE iteration, retained exact
  requests, retry/discard, and resynchronization and calls those named actions
  explicitly.
- React provider/hooks, surface host, operations, forms, review, navigation,
  status/error, and lazy Navgraph primitives.

Presentation state contains only rendered conversation messages, status,
error, review, and retained-request display. It is not an alternate
`RouteDeckObservableState`, and there is no public generic reducer/dispatch or
transition callback API.

## Evidence

```powershell
pnpm --filter @routedeck/core test
pnpm --filter @routedeck/core typecheck
pnpm --filter @routedeck/react typecheck
pnpm --filter @routedeck/react test
```

Update this document when strict decoding, assistant/chat clients, observable
state, named presentation actions, retained-request behavior, routing/history,
forms, or React primitive ownership changes.
