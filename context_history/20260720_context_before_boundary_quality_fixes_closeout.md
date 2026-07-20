# RouteDeck Context Before Boundary Quality Fixes Closeout

Archived: 2026-07-20 before replacing the pre-fix audit state with the
implemented post-fix restart snapshot.

Last updated: 2026-07-20
Status: feature-owned composition and the framework-built runtime are
implemented. The current structural boundary report passes, but the quality
audit identifies remaining conversation, session-selection, copy, and
duplication gaps. Execution is local Windows only.

## Start Here

1. [Critical prompt](./critical_prompt.md)
2. [ADR-006 runtime/conversation boundary](./decisions/ADR-006-framework-owned-runtime-and-conversation-boundary.md)
3. [RouteDeck reference](./docs/route-deck-reference.md)
4. [Feature and architecture coverage](./architecture/feature-coverage.md)
5. [Subsystem code map](./architecture/code-map.md)
6. [System flow index](./SYSTEM_FLOW_INDEX.md)
7. [Test index](./test_index/README.md)
8. [Documentation authority map](./architecture/documentation-map.md)
9. [Current quality and boundary audit](./audits/2026-07-20-routedeck-quality-boundary-audit.md)
10. [Active boundary and quality fix plan](./plans/2026-07-20-routedeck-boundary-quality-fixes.md)

ADR-006 controls runtime assembly and generic conversation. Non-superseded
ADR-005 controls named state/feature structure. ADR-004 controls scope,
product/framework separation, and local execution. Completed plans/designs are
under `docs/archive/` and are not active authority.

## Current Implementation

- Product developers author `Feature` modules with complete `Node` objects and
  node-owned outgoing transitions. A small `Application` selects features and
  the entry node; RouteDeck derives incoming adjacency and compiles one graph
  and frontend contract.
- Exact `FeatureBindings` supply product handlers/providers/guards. Duplicate,
  missing, extra, synchronous, or malformed ownership fails at startup.
- One `RouteDeckRuntime` owns canonical sessions, projection, one operation
  runner, navigation over that runner, optional agent driver, and lifecycle.
- SQLAlchemy supports explicit SQLite/PostgreSQL URLs with leases, journals,
  events, encrypted blobs, retention, reopen, and restart recovery.
- FastAPI exposes one runtime-derived `/api/routedeck` plane for contract,
  sessions, operations/reviews, navigation, conversation, events, private
  forms, and inspection.
- The optional LangGraph adapter drives product-supplied user/assistant graphs,
  rebuilds durable conversation, filters model context/tools, and supervises
  every product tool through the same runner. RouteDeck owns no product graph
  topology, prompt, model, or wording.
- `@routedeck/core` owns strict browser contracts, bootstrap/resync, retained
  request identity, routing/history, forms, and the authoritative browser
  mirror. `@routedeck/react` supplies product-neutral presentation and UI
  primitives, including the read-only Navgraph.

## Medusa Reference Consumer

The Medusa app owns real Store API transport and all catalog, cart, checkout,
order, market, prompt/model/graph, product session, readiness, component, and
local-stack behavior. RouteDeck contains no commerce endpoint or fallback path.

Its four feature modules declare the buyer navgraph. Chat, surfaces, and hybrid
interactions converge on the framework runner. The browser never calls
`/store/*`; real IDs remain behind scoped opaque handles. Checkout private
values remain encrypted and excluded from public/model state. Order placement
uses required review and explicit delivery/reconciliation semantics.

The browser automatically creates a guest session on a missing, expired, or
contract-mismatched bootstrap only when the incoming route is shareable. It
then enters the captured path through normal supervised navigation. A
session-bound link never creates replacement state. Initial greeting starts
through the generic assistant-initiated conversation path after bootstrap when
durable conversation is empty.

## Current Quality And Boundary Status

- The schema-3 static boundary report passes 8/8 checks with 0 violations:
  core remains product-neutral by dependency, Store endpoints stay in the
  Medusa client, the browser has no Store path, runtime/transport use one
  framework-built runner, and LangGraph topology remains product-owned.
- Ruff passes for the maintained Python production paths. Core, React, and
  Medusa TypeScript typechecks pass.
- Total separation is not yet achieved. Medusa's initial-conversation module
  still owns generic assistant-stream validation/convergence, and generic
  core/React packages contain buyer-specific error wording.
- Review accept/reject still allow an omitted session ID to select a configured
  default session. The Medusa local host hardcodes that default and local
  runtime/cookie policy.
- Product-internal drift risks remain in duplicated contact fingerprints,
  backend surface schemas versus frontend decoders, repeated RouteDeck
  current-node lookup, and unused frontend operation ID mirrors.

## Known Gaps

- The current FastAPI/Medusa guest adapter selects one session through an
  HTTP-only cookie. Separate browser profiles are isolated; tabs in one profile
  share the guest session. Authenticated user/tenant authorization and an
  opaque multi-session resolver are not implemented.
- The guest cookie carries the internal session ID and defaults to
  `secure=False`; this is acceptable only for the explicitly local HTTP demo.
- A reusable headless assistant-initiation coordinator is not implemented.
  Medusa currently duplicates generic request/event/synchronization behavior.
- Public release remains unclaimed until a current clean-install/package and
  consolidated release run produces sanitized evidence.
- No test, real-commerce, or live-model E2E pass is implied by this context.
  Use the exact current command output and artifact path for any such claim.

## Current Maintenance Contract

- `architecture/feature-coverage.md` must cover every supported feature.
- `architecture/code-map.md` maps every maintained live source file to an owner.
- `python scripts/check_doc_coverage.py` scans live source without Git.
- `python scripts/check_context_architecture.py` checks canonical links and
  retired vocabulary.
- `audits/2026-07-20-routedeck-quality-boundary-audit.md` records current
  hardcoding, separation, duplication, checker blind spots, and next steps.
- Only active decision-complete work belongs in `plans/` or current
  `docs/superpowers/`; completed material is archived.

## Next Step

The active implementation plan is
`plans/2026-07-20-routedeck-boundary-quality-fixes.md`. It resolves QB-01 through
QB-08 in seven focused slices: assistant-turn coordination, explicit review
session identity, host-owned session selection/deployment policy, neutral copy
and boundary scanners, contact fingerprint consolidation, compiled node
lookup, and surface-schema/decoder parity plus proven dead-code cleanup. Each
slice has targeted proof; the protected real-Medusa/live-model checkout video
runs once as the final behavior gate.

Services, databases, tests, and browser automation run locally on Windows. Do
not probe or fall back to another host. When starting the protected Medusa
stack, report the command and smoke URLs from the test index.
