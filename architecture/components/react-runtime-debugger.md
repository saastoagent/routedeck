# Headless And React Runtime

## Purpose

`@routedeck/core` is the headless browser client and RouteDeck projection-state
layer. `@routedeck/react` supplies product-neutral React bindings and UI
primitives. `@routedeck/testing` owns test-only harnesses.

## Owner Files

- `packages/core/src/{contracts,client,store,routing,private-forms}/*`
- `packages/core/src/index.ts`
- `packages/react/src/{provider,hooks,surfaces,navigation,private-forms,review,status,inspector}/*`
- `packages/react/src/index.ts`
- `packages/testing/src/*`

## Public Interfaces

- `@routedeck/core`: strict decoding, HTTP/SSE, retained replay/resync,
  observable named actions/selectors, history control, and private-form state.
- `@routedeck/react`: provider/hooks, surface registry/host, operation
  controller, navigation, forms, review, status/error, and lazy navgraph.
- `@routedeck/testing`: factories plus component/store/SSE harnesses used only
  in tests.

The headless store owns the canonical browser view of RouteDeck state. Product
chat state is separate and may synchronize to a session/projection version, but
it cannot infer commerce state or replace the RouteDeck projection.

## Evidence

```powershell
pnpm --filter @routedeck/core test
pnpm --filter @routedeck/react test
pnpm --filter @routedeck/testing test
pnpm typecheck
pnpm build
```
