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
- `packages/core/src/conversation/{types,codec,client,assistant}.ts`
- `packages/core/src/store/{store,bootstrap,recovery,synchronization,operations,lifecycle}.ts`
- `packages/core/src/{client,routing,private-forms}/*`
- `packages/react/src/bootstrap/*`
- `packages/react/src/conversation/{presentation,useRouteDeckConversation}.ts`
- `packages/react/src/{provider,hooks,surfaces,navigation,private-forms,review,status,inspector}/*`
- `packages/testing/src/*`

## Public Interfaces

- `createRouteDeckAgentClient(...)` loads canonical conversation, streams user
  chat, and streams typed assistant initiation through
  `streamAssistantTurn(...)`.
- `runAssistantInitiatedTurn(...)` owns request/event validation, durable
  completion proof, version synchronization, conflict convergence, and final
  conversation reload for headless assistant-only turns. Its optional typed
  progress observer publishes accumulated assistant text after every validated
  delta, before terminal completion, without exposing the raw stream state
  machine to consumers.
- `createRouteDeckStore(...)` remains the public coordinator facade; focused
  bootstrap, synchronization, operation, and lifecycle coordinators are
  internal.
- `selectRouteDeckBootstrapRecovery(...)` is the product-neutral recovery
  descriptor, and `runRouteDeckBootstrapRecoveryAction(...)` rechecks and
  executes only a currently legal action. Both are owned by core.
- `RouteDeckObservableState` and named store actions/selectors remain the
  canonical browser view of session/projection state.
- `RouteDeckSurfaceHost` validates the complete product component registry
  against the compiled frontend contract before rendering. Missing components
  and stale extra registrations produce the visible
  `surface_registry_mismatch` failure.
- `useRouteDeckConversationInputPolicy()` resolves the current node's typed,
  static conversation-input contract. The framework owns contract validation
  and current-node lookup; the consumer owns node declarations and disabled
  wording.
- `useRouteDeckBootstrapRecovery(store)` adapts the core recovery descriptor to
  loading, ready, disposed, or product-rendered recovery and attaches action
  runners through the core executor. It does not expose retained request IDs,
  reconstruct legality, or make product policy decisions. After a store first
  reaches ready, projection resync/reconnect work remains background work and
  does not unmount the product application; a terminal synchronization error
  still returns to explicit recovery.
- `RouteDeckBootstrapBoundary` starts an idle store and gates product children
  on initial readiness while preserving those children across later background
  synchronization; consumers supply loading and recovery rendering.
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

## Product Boundary

Generic core/React production messages are product-neutral. A consumer may wrap
framework error codes with product-specific wording, but it must not inspect the
assistant stream or reproduce the coordinator or bootstrap recovery state
machines. Medusa renders its product recovery shell from the normalized React
adapter and its initial conversation module chooses greeting request identity
and copy before delegating the lifecycle to `runAssistantInitiatedTurn(...)`;
it may render the coordinator's typed accumulated progress directly.

## Evidence

```powershell
pnpm --filter @routedeck/core test
pnpm --dir packages/core exec vitest run --config vitest.config.ts src/conversation/assistant.test.ts
pnpm --filter @routedeck/core typecheck
pnpm --filter @routedeck/react typecheck
pnpm --filter @routedeck/react test
```

Update this document when strict decoding, assistant/chat clients, observable
state, named presentation actions, retained-request behavior, routing/history,
forms, surface-registry enforcement, conversation-input policy, or React
primitive ownership changes.
