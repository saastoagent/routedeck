# Runtime Boundary Implementation Coverage

Verified: 2026-07-20

This document is the reusable source-to-contract-to-proof crosswalk for the
RouteDeck/Medusa boundary remediation completed in commit `e82714e`. It records
verified implementation facts. It does not override ADR-006, non-superseded
ADR-005, ADR-004, `docs/route-deck-reference.md`, or current source.

## Complete Remediation Crosswalk

| Finding | Implemented behavior | RouteDeck owner | Medusa owner | Canonical contract | Focused proof |
| --- | --- | --- | --- | --- | --- |
| QB-01 assistant-turn duplication | One reusable headless coordinator validates assistant events, proves durable completion, converges versions, handles conflicts, and reloads canonical conversation. | `packages/core/src/conversation/assistant.ts`, conversation client/codec exports, React conversation hook. | `frontend/src/app/initialConversation.ts` owns greeting policy, request identity, and buyer-facing failure copy only. | ADR-006; headless/React component contract; user/assistant conversation feature row. | `packages/core/src/conversation/assistant.test.ts` plus Medusa initial-conversation tests. |
| QB-02 implicit review identity | Review accept/reject require a non-empty keyword-only session ID through core, persistence, FastAPI, and product call sites. No `default_session_id` execution path remains. | `routedeck_core/supervision/review_*.py`, runner support, FastAPI operation routes, SQLAlchemy opener. | Product binding and tests pass the session selected by the host. | ADR-005 named actions; ADR-006 host boundary; review feature row. | Review lifecycle, fail-closed, runtime-builder, persistence, FastAPI, and Medusa binding tests. |
| QB-03 product copy in generic packages | Generic Python/TypeScript production copy is product-neutral and checked structurally. | Generic conversation contracts, FastAPI transport, core/React presentation. | Medusa owns buyer wording and translation. | ADR-006; React and FastAPI component contracts. | Schema-4 vocabulary scanner and negative tests. |
| QB-04 session/deployment ownership | Every generic HTTP plane requires `RouteDeckSessionSelector`; guest-cookie mode is explicit and cookie/origin/worker/TTL/instance values are host configuration. | `routedeck_fastapi/dependencies.py`, `session_http.py`, router/runtime derivation. | `backend/main.py`, product settings/runtime, Compose and protected stack select local guest policy. | ADR-004 deployment boundary; ADR-006 transport boundary; generic HTTP and product-runtime feature rows. | `tests/fastapi/test_session_selection.py`, transport tests, Medusa config/readiness tests, schema-4 boundary report. |
| QB-05 contact identity duplication | One product-owned algorithm derives the contact identity consumed by checkout and orders. | No framework implementation; RouteDeck protects private state and opaque handles only. | `backend/medusa_agent/contact_identity.py` and checkout/order models. | ADR-004; Medusa checkout/orders feature rows. | `test_contact_identity.py` plus real-Medusa cart/delivery coverage. |
| QB-06 backend/frontend surface drift | Sixteen valid/invalid vectors exercise the compiled backend schemas and eight corresponding frontend decoders. | RouteDeck compiles surface schemas and hosts generic surface primitives. | `contracts/surface-props-parity.json`, backend parity test, frontend parity test and eight product decoders. | ADR-004; product-surface parity coverage row; Medusa component contract. | One backend contract test and 17 frontend parity checks. |
| QB-07 repeated current-node scans | One immutable compiled node mapping is validated against graph identity and used through `require_node(...)`. | `routedeck_core/app/compiled.py` and compiler; context, projection, navigation, and supervision consumers. | Medusa consumes compiled contracts and owns no alternate lookup. | ADR-005; feature-authoring and compiled-runtime rows; core runtime component. | Compiled-contract, context, projection, navigation, supervision, runtime, and persistence tests. |
| QB-08 dead mirrors and size audit | Two proven-unused frontend operation mirrors were removed. Remaining large modules are watch points, not duplicate authorities and were not rewritten without feature need. | No compatibility aliases added. | Obsolete Medusa frontend constants removed. | ADR-005 no-shim consequence; post-fix quality audit. | Typecheck, focused frontend checks, import/search evidence, schema-4 boundary report. |

## Code-Map Ownership Coverage

All 102 files in `e82714e` fall under these existing code-map owners:

- compiled application and interaction runtime;
- SQLAlchemy persistence and recovery;
- FastAPI conversation and transport;
- headless TypeScript runtime;
- React primitives;
- standalone Medusa reference consumer;
- architecture and context governance;
- validation and release tooling.

`python scripts/check_doc_coverage.py` independently maps all 574 maintained
source/documentation files to a code-map row. That check proves file ownership,
while the remediation table above proves the semantic behavior-to-contract
relationship. Neither check alone substitutes for the other.

## Boundary Invariants Now Enforced

- RouteDeck constructs one generic runtime/runner/navigation path.
- The host chooses and authorizes the session; RouteDeck validates the selected
  internal ID and never falls back to another session.
- RouteDeck owns generic user/assistant turn mechanics; the consumer owns graph,
  model, prompt, policy, and wording.
- Medusa owns Store transport, commerce facts, contact identity, product
  schemas/decoders, UI, and deployment policy.
- The browser does not call Medusa `/store/*` directly.
- Missing configuration, selector, graph, model, Store dependency, or invariant
  fails visibly without a synthetic substitute.

## Runtime Evidence Boundary

The current retained behavior proof is the local live-model Playwright run at
`artifacts/boundary-quality-live-checkout-20260720-165922/`: one test passed in
2.2 minutes and produced a 1920x1080, 25 fps, 116.12-second uninterrupted video.
It shows a curious discovery conversation, product clarification, hybrid cart
and checkout, visible deep links, a permanently open Navgraph, required review,
and real order confirmation without reload. Artifacts are local run evidence
and are intentionally not architectural authority or committed source.

## Explicit Remaining Boundary

RouteDeck provides the selector protocol but does not implement a product's
authentication, user/tenant model, session listing, or principal-aware opaque
multi-session authorization. That remains a consumer integration and must be
proved with cross-principal denial before it can be claimed.
