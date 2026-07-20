# RouteDeck Quality And Boundary Post-Fix Audit

Date: 2026-07-20
Scope: the seven-slice remediation of QB-01 through QB-08, current maintained
RouteDeck source, and the standalone Medusa reference consumer.
Runtime: local Windows development machine and the protected local Docker
stack only.

## Verdict

The audited RouteDeck/Medusa runtime boundary is now clean for the implemented
architecture. The schema-4 structural report passes with zero violations, all
seven planned remediation slices have focused proof, the real Store API lane
passes, and one live-model checkout reaches a real order confirmation in an
uninterrupted 1920x1080 recording.

This is not a claim that RouteDeck owns authentication or that every future
consumer is automatically multi-user safe. RouteDeck now requires the correct
host-owned `RouteDeckSessionSelector` seam; the consumer must implement and
test its own principal/session authorization. The Medusa demo deliberately
chooses one guest cookie per browser profile.

## Finding Closure

| ID | Result | Current evidence |
| --- | --- | --- |
| QB-01 | Closed | `@routedeck/core` owns `runAssistantInitiatedTurn(...)`; Medusa supplies greeting identity/copy and contains no production `.streamAssistantTurn(...)` state machine. |
| QB-02 | Closed | Review accept/reject require a non-empty keyword-only `session_id`; `default_session_id` is absent from maintained source and tests. |
| QB-03 | Closed | Generic production packages use product-neutral conversation wording; schema 4 rejects buyer vocabulary in generic TypeScript/Python source. |
| QB-04 | Closed for framework seam and demo policy | `RouteDeckSessionSelector` is required; `GuestCookieSessionSelector` is explicit; Medusa requires instance, TTL, worker, cookie, and browser-origin configuration. A principal-aware production adapter remains consumer work, not RouteDeck work. |
| QB-05 | Closed | Checkout and orders use one product-owned `contact_identity.py` implementation with typed parity tests. |
| QB-06 | Closed for the eight maintained product decoders in scope | Sixteen checked-in valid/invalid vectors run against compiled backend schemas and the matching frontend decoders. Conditional/undeclared surfaces are not implied. |
| QB-07 | Closed | `CompiledApplication` owns an immutable graph-identity-checked node map and `require_node(...)`; runtime subsystems no longer repeat node scans. |
| QB-08 | Partially closed by design | The unused frontend operation mirrors were removed. Nine maintained production modules remain above 400 lines; size alone is not a boundary defect and the approved plan did not authorize broad behavior-preserving decomposition. |

## Boundary Separation

| Boundary | Status | Detail |
| --- | --- | --- |
| Feature composition | Separated | Consumers author complete feature nodes and outgoing transitions; RouteDeck compiles composition, derives incoming adjacency, and owns graph indexes/contracts. |
| Runtime and supervision | Separated | RouteDeck builds one runner/runtime/navigation path; Medusa supplies bindings, callbacks, graphs, and configuration. |
| Conversation lifecycle | Separated | RouteDeck owns generic driver/turn/SSE/headless convergence; Medusa owns prompt, model, topology, greeting policy, and buyer-facing copy. |
| Commerce | Separated | Store transport, IDs, catalog/cart/checkout/order behavior, contact identity, and reconciliation stay in Medusa. The browser has no `/store/*` path. |
| Session selection | Separated seam | FastAPI requires a host selector. RouteDeck validates one selected internal ID; the host owns authentication, authorization, users, tenants, and opaque handles. |
| UI and surfaces | Separated | RouteDeck owns generic store/React primitives and Navgraph; Medusa owns components, markdown styling, product decoders, and surface copy. |
| Deployment policy | Separated | Medusa host configuration owns instance/TTL/worker/origin/cookie choices. The framework has no implicit guest selector or insecure cookie default. |

## Hardcoding Audit

Allowed product facts remain in the Medusa consumer: operation/node/surface
identifiers, route templates, catalog wording, model-role names, and protected
demo seed values. These are product declarations, not RouteDeck branches.

Allowed local deployment values remain in `demo-stack.ps1`: fixed localhost
ports, one worker, explicit TTLs, cookie name/path, and
`ROUTEDECK_GUEST_COOKIE_SECURE=false`. They are generated into the protected
local environment and are visibly local-only. The Medusa runtime model requires
the corresponding settings and does not silently substitute them.

No audited hardcoding violation remains. `medusa_timeout_seconds=15.0` is a
named Medusa client setting with an overridable product default, and generic
SSE batch/heartbeat defaults remain framework-level behavior; neither selects a
product, identity, provider, or fallback.

## Duplication And Maintainability

- The contact fingerprint has one owner.
- The product frontend no longer mirrors the two unused operation constants.
- The assistant-initiation state machine has one generic owner.
- The current-node lookup has one compiled owner.
- Backend/frontend surface validation is intentionally duplicated by language,
  but drift is now checked through one shared vector contract.
- Remaining production modules above 400 lines are:
  `routedeck_core/navigation/routes.py` (414),
  `routedeck_core/supervision/outcome_commits.py` (482),
  `routedeck_core/supervision/outcome_results.py` (402),
  `routedeck_sqlalchemy/sessions.py` (404),
  `routedeck_sqlalchemy/store.py` (447),
  `packages/core/src/routing/codec.ts` (401),
  `features/catalog/providers.py` (405),
  `features/checkout/models.py` (453), and
  `features/checkout/providers.py` (471).

These files are maintainability watch points, not evidence of duplicate state
authority. Split them only around a concrete feature or demonstrated change
hazard; do not perform a line-count-only rewrite.

## Runtime Findings

The successful live story used natural discovery, product clarification,
variant selection, a change of quantity/mind, chat-driven cart navigation,
surface-driven checkout, required review, and real order confirmation. The
synthetic address bar and permanent Navgraph prove deep-link and current-node
movement without reload.

Two earlier diagnostic recordings were correctly retained as failures. One
showed the live model asking for redundant cart confirmation; that is agent
design variability, not a RouteDeck transition/boundary fault. Another showed a
successful private-form `PUT` taking 13.5 seconds and the following resync
exceeding the original 20-second E2E observation window. The harness now allows
60 seconds for real checkout stage convergence; product behavior was not
changed. The later uninterrupted run passed.

## Current Evidence

- Boundary report:
  `C:\Users\ragha\AppData\Local\Temp\routedeck-boundaries-final.json` — schema
  4, pass, zero violations.
- Real Store API integration:
  `python -m pytest examples/medusa-agent/backend/tests/integration/real_medusa -q`
  — 4 passed in 21.131 seconds; JUnit at
  `C:\Users\ragha\AppData\Local\Temp\routedeck-real-medusa.xml`.
- Live browser:
  `pnpm --filter @routedeck/medusa-agent-e2e exec playwright test --config live-checkout-video.playwright.config.ts human-checkout-flow.spec.ts`
  — 1 passed in 2.4 minutes.
- Video: 1920x1080, 25 fps, 130.84 seconds, 11,784,139 bytes at
  `artifacts/boundary-quality-live-checkout-20260720-160830/raw-results/human-checkout-flow--human-7f281-th-visible-navigation-proof-desktop-chromium/video.webm`.
- Final screenshot and trace are retained beside the video. The Playwright
  `.last-run.json` records `status: passed` and no failed tests.

## Suggested Next Steps

1. Build one example production-style authenticated selector in a separate
   consumer integration, with two principals, two sessions per principal, and
   explicit cross-principal denial. This proves consumer composition without
   moving identity into RouteDeck.
2. Add timing telemetry around private-form save and session resync, then decide
   from measured percentiles whether the protected local stack has a real
   performance problem. Do not infer one from a single slow request.
3. Tune the Medusa agent prompt/evaluation for unnecessary confirmation turns.
   Keep this classified as product agent design unless a trace proves an
   incorrect legal-operation or transition projection.
4. Decompose a large module only when a feature touches it and a cohesive owner
   can be extracted with focused regression proof.
5. Run the destructive clean release/packaging harness only when public release
   proof is explicitly requested. This audit does not claim that gate.
