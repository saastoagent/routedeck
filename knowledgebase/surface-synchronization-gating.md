# Surface Synchronization Gating Crosswalk

Verified: 2026-08-06

## Contract

A projected Surface may remain mounted during authoritative browser
synchronization, but it must not dispatch while the canonical store is not
`live`. `RouteDeckSurfaceHost` owns this product-neutral gate. Consumers own
their component rendering and copy; they do not recreate store readiness.

## Implementation To Contract To Proof

| Layer | Owner | Evidence |
| --- | --- | --- |
| Canonical store readiness | `@routedeck/core` | `RouteDeckClientState.syncStatus`; operation coordinator rejects non-live dispatch |
| React interaction boundary | `packages/react/src/surfaces/RouteDeckSurfaceHost.tsx` | non-live stores mark projected Surface sections busy/inert and fail direct affordance invocation as `store_not_ready` |
| Framework regression | `packages/react/src/surfaces/RouteDeckSurfaceHost.test.tsx` | resynchronizing projected Surface renders `aria-busy=true` and `inert` |
| Canonical contract | `docs/route-deck-reference.md` | Surface Contract and Headless/React package sections |
| Consumer acceptance | Corpus `scripts/run_public_lounge_recording.py` | run `20260806T173245Z-898d846f57`: public chat -> Sign in -> Back to Lounge passed 2/2 with zero HTTP, console, or page errors |

The pre-fix failure remains useful negative evidence: a stale Sign-in Surface
could invoke Back to Lounge while `syncStatus="resyncing"`, and the operation
coordinator correctly rejected the non-live store. The fix does not weaken
that fail-closed coordinator; it prevents the invalid interaction one layer
earlier at the framework-owned React boundary.

## Update Trigger

Revalidate this crosswalk whenever Surface dispatch, store synchronization
status, bootstrap/recovery mounting, or consumer affordance composition
changes.
