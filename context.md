# RouteDeck Current Context

Updated: 2026-08-06
Status: public source repository; surface synchronization gating complete and
ready for publication on `main`. No PyPI or npm registry publication is
claimed.

## Current Authority

1. `critical_prompt.md`
2. `decisions/ADR-006-framework-owned-runtime-and-conversation-boundary.md`
3. `docs/route-deck-reference.md`
4. `architecture/feature-coverage.md`
5. `architecture/code-map.md`
6. `architecture/components/react-runtime-debugger.md`
7. `test_index/README.md`
8. `context_checkpoints/context_checkpoint_06-08-2026-1150PM.md`

RouteDeck owns reusable interaction state, synchronization, supervision,
navigation, projection, persistence ports, transport, and product-neutral
React primitives. Consuming products own authentication, domain truth,
prompts/models, business handlers, product components, copy, and deployment.

## Completed Lifecycle Contract

`RouteDeckSurfaceHost` keeps projected Surfaces mounted but busy and inert
whenever the canonical client store is not `live`. This covers bootstrap,
navigation, reconnect, and resynchronization. If an affordance is invoked
during that window, the host fails `store_not_ready`; it never bypasses the
existing operation coordinator.

The contract, feature coverage, React component contract, flow index, consumer
guide, test index, and cross-owner knowledgebase trace are aligned. The change
does not alter Surface declarations, operation supervision, product components,
or the consumer/framework ownership boundary.

## Current Evidence

- `pnpm --filter @routedeck/react test` -> 23/23 tests passed.
- `pnpm --filter @routedeck/react typecheck` -> passed.
- `pnpm --filter @routedeck/react build` -> passed.
- Corpus acceptance run `20260806T173245Z-898d846f57` exercised public chat ->
  Sign in -> Back to Lounge on an isolated local stack and passed 2/2 with zero
  HTTP, console, or page errors.
- Documentation coverage and context architecture gates are recorded in
  `logs/20260806_2350_surface_sync_gating.md`.

## Known Gaps And Publication

RouteDeck remains public at `https://github.com/saastoagent/routedeck`. Registry
package ownership, trusted publishers, alpha version selection, publication,
and clean registry-install verification remain pending. The principal-aware
multi-session example and coverage-hardening plan also remain open.

Historical untracked `artifacts/` and root `design-qa.md` are excluded from
this closeout and publication.

## Restart Owners

- Checkpoint: `context_checkpoints/context_checkpoint_06-08-2026-1150PM.md`
- Session log: `logs/20260806_2350_surface_sync_gating.md`
- Semantic crosswalk: `knowledgebase/surface-synchronization-gating.md`
- Canonical contract: `docs/route-deck-reference.md`
- React component: `architecture/components/react-runtime-debugger.md`
- Validation: `test_index/README.md`
