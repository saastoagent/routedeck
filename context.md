# RouteDeck Context

Last updated: 2026-07-20
Status: the seven boundary/quality remediation slices are implemented and
focused static, real-Medusa, and live checkout gates pass. Work is local Windows
only. This context is part of the user-requested boundary-quality closeout
commit; no push or deployment is implied.

## Start Here

1. [Critical prompt](./critical_prompt.md)
2. [ADR-006 runtime/conversation boundary](./decisions/ADR-006-framework-owned-runtime-and-conversation-boundary.md)
3. [RouteDeck reference](./docs/route-deck-reference.md)
4. [Feature and architecture coverage](./architecture/feature-coverage.md)
5. [Subsystem code map](./architecture/code-map.md)
6. [System flow index](./SYSTEM_FLOW_INDEX.md)
7. [Test index](./test_index/README.md)
8. [Post-fix quality and boundary audit](./audits/2026-07-20-routedeck-quality-boundary-post-fix-audit.md)
9. [Latest checkpoint](./context_checkpoints/context_checkpoint_20-07-2026-4-25PM.md)

ADR-006 controls runtime assembly and generic conversation. Non-superseded
ADR-005 controls named state/feature structure. ADR-004 controls scope,
product/framework separation, and local execution. The completed seven-slice
plan is historical material under `docs/archive/`.

## Current Architecture

- Product developers author independently owned `Feature` modules with complete
  `Node`s and node-owned outgoing transitions. A small `Application` selects
  features and the entry node; RouteDeck validates composition, derives
  incoming adjacency, and compiles the frontend contract and immutable node
  index.
- Exact `FeatureBindings` supply product async handlers/providers/guards.
  Missing, extra, duplicate, synchronous, or malformed ownership fails at
  startup.
- One `RouteDeckRuntime` owns canonical sessions, projection, one operation
  runner, navigation over that runner, optional generic agent driver, and
  explicit lifecycle.
- Review accept/reject requires the host-selected non-empty session ID. FastAPI
  requires a host-owned `RouteDeckSessionSelector`; RouteDeck does not own
  authentication, users, tenants, session listing, or authorization.
- The optional LangGraph adapter drives product-supplied graphs, rebuilds
  durable conversation, filters context/tools, and supervises product tools.
  `@routedeck/core` owns reusable assistant-only turn convergence. Prompts,
  models, topology, greeting policy, and wording remain consumer-owned.
- `@routedeck/core` owns strict browser contracts, bootstrap/resync, routing,
  retained request identity, forms, and authoritative browser state.
  `@routedeck/react` supplies product-neutral UI primitives and the read-only
  Navgraph.

## Medusa Reference Consumer

Medusa owns the real Store client and all catalog, cart, checkout, order,
market, prompt/model/graph, product-session, deployment-policy, UI, and local
stack behavior. The browser never calls `/store/*`; real IDs remain behind
scoped opaque handles. Private contact values remain encrypted and outside
public/model state. Reviewed placement preserves delivery evidence and explicit
reconciliation semantics.

The local host explicitly uses `GuestCookieSessionSelector`; separate browser
profiles receive separate guest sessions and tabs in one profile share one.
Production authenticated multi-session selection is a consumer adapter over
the implemented selector seam. Checkout and orders share one contact identity
algorithm. Sixteen vectors check the compiled schemas and eight corresponding
frontend surface decoders.

## Current Evidence

- Schema-4 boundary report: pass, zero violations at
  `C:\Users\ragha\AppData\Local\Temp\routedeck-boundaries-final.json`.
- Maintained Python Ruff and core/React/Medusa TypeScript typechecks pass.
- Focused tests for assistant coordination, explicit review session identity,
  selector/host policy, neutral copy/scanners, contact identity, compiled node
  lookup, and surface parity pass.
- Real Medusa integration: 4 passed in 21.131 seconds against
  `http://127.0.0.1:9100`.
- Live checkout: 1 passed in 2.4 minutes at `http://127.0.0.1:5198`, using the
  live model and real Store API. The uninterrupted 1920x1080 video is
  [video.webm](./artifacts/boundary-quality-live-checkout-20260720-160830/raw-results/human-checkout-flow--human-7f281-th-visible-navigation-proof-desktop-chromium/video.webm).

Only these named current runs support pass claims. The protected stack should
not be assumed running in a later session.

## Known Gaps And Next Step

- A production principal-aware selector example is not implemented. Add it in
  a consumer integration with two users, multiple sessions, and cross-user
  denial; do not move identity policy into RouteDeck.
- One diagnostic live run showed unnecessary cart confirmation from the model.
  That is Medusa agent-design variability unless a trace proves a RouteDeck
  transition error.
- One private-form save was transiently slow in the protected local stack.
  Instrument save/resync timing before making a performance change.
- Nine maintained production modules exceed 400 lines. Treat them as
  feature-driven refactor candidates, not boundary defects.
- Public release remains unclaimed until an explicitly authorized clean
  packaging/release run produces sanitized evidence.

The next recommended feature is the authenticated consumer selector example
plus measured multi-user/session E2E proof. Use focused tests during the feature
and one real E2E at its end.

## Maintenance Contract

`architecture/feature-coverage.md` owns capability coverage;
`architecture/code-map.md` owns subsystem/source mapping;
`test_index/README.md` owns validation meaning. Run
`python scripts/check_doc_coverage.py` and
`python scripts/check_context_architecture.py` after changing these surfaces.
Archive completed plans/designs so historical material cannot compete with
current authority.
