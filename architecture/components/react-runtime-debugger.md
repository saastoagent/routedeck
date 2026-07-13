# Headless And React Runtime

## Purpose

This component owns the current frontend framework split. `@routedeck/core` is
the headless client and authoritative browser-state layer;
`@routedeck/react` supplies React bindings and product-neutral UI primitives on
top of it. `@routedeck/testing` owns test-only harnesses.

## Owner Files

- `packages/core/src/contracts/*`
- `packages/core/src/client/*`
- `packages/core/src/store/*`
- `packages/core/src/routing/*`
- `packages/core/src/private-forms/*`
- `packages/core/src/index.ts`
- `packages/react/src/provider/*`
- `packages/react/src/hooks/*`
- `packages/react/src/surfaces/*`
- `packages/react/src/navigation/*`
- `packages/react/src/private-forms/*`
- `packages/react/src/review/*`
- `packages/react/src/status/*`
- `packages/react/src/inspector/*`
- `packages/react/src/index.ts`
- `packages/testing/src/*`

Top-level `react/` is a deprecated Corpus-only compatibility tree. It does not
own the current package contract; see `react/README.md` for its removal gate.

## Public Interfaces

- `@routedeck/core`: generated contract decoding, HTTP/SSE clients, replay and
  resync, observable state with named actions and selectors, route/history
  control, and private-form state.
- `@routedeck/react`: provider and hooks, surface registry/host, operation
  controller, navigation/history sync, private-form hooks/components, review,
  needs-input, status/error, and lazy navgraph inspector APIs.
- `@routedeck/testing`: explicit factories plus component, store, and SSE test
  harnesses; never a product data or runtime fallback.

## Dependent Flows

- Product React shells consuming public RouteDeck projections.
- Cursor-aware SSE replay and authoritative observable-store actions.
- Exact browser-history reconciliation and active-surface hydration.
- Private-form lifecycle, review, needs-input, status, and recovery UI.
- Lazy topology inspection without creating a second state authority.

The headless store keeps its public facade in `store/store.ts`; observable
state, navigation actions, route synchronization, event-stream lifecycle,
errors, and public types live in separate modules. The React Navgraph similarly
separates topology/orchestration, node rendering, shared inspector UI, and
styles.

## Tests And Evidence

```powershell
pnpm --filter @routedeck/core test
pnpm --filter @routedeck/react test
pnpm --filter @routedeck/testing test
pnpm typecheck
pnpm build
```

Package-owned Vitest projects cover `packages/core`, `packages/react`, and
`packages/testing`; the root workspace coordinates them without discovering
legacy `react/tests` as current unit coverage.

## Update Triggers

Update this doc and `architecture/code-map.md` when changing generated
contracts, client/replay semantics, store state, routing/history, private-form
ownership, hooks, surfaces, review/status behavior, inspector topology, package
exports, or test ownership.
