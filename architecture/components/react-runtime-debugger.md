# React Runtime And Debugger

## Purpose

This component owns `@routedeck/react`: RouteDeck's frontend store, provider,
hooks, surfaces, operation readiness helpers, location state, debugger topology,
and TypeScript contracts.

## Owner Files

- `react/src/index.ts`
- `react/src/types.ts`
- `react/src/RouteDeckProvider.tsx`
- `react/src/RouteDeckStore.ts`
- `react/src/RouteDeckSurface.ts`
- `react/src/RouteDeckLocation.ts`
- `react/src/RouteDeckDebugger.tsx`
- `react/src/routeDeckDebuggerRouting.ts`
- `react/src/routeDeckDebuggerTopology.ts`
- `react/src/operationReadiness.ts`

## Public Interfaces

- `RouteDeckProvider`
- RouteDeck store and hooks
- debugger components
- location helpers
- operation readiness helpers
- exported TypeScript contracts

## Dependent Flows

- Product React shells consuming RouteDeck projections.
- Diagnostics dock/fullscreen debugger views.
- Topology-only graph inspection.
- Browser location replay and active-surface hydration.
- Quick-action readiness and pending/blocked operation display.

## Tests And Evidence

- `react/tests/*.mjs`
- `react/tests/*.tsx`
- `cd react && npm test`

## Update Triggers

Update this doc and `architecture/code-map.md` when changing:

- store contract or hook return shape
- exported TypeScript types
- operation readiness interpretation
- debugger routing/topology behavior
- location or navigation state behavior
- package exports or test command
