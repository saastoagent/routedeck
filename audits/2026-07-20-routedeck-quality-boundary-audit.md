# RouteDeck Quality And Boundary Audit

Date: 2026-07-20
Repository: `D:\Dev\AI Projects\routedeck`
Runtime location: local Windows
Mode: source and documentation audit; no product implementation changes

## Verdict

RouteDeck's structural backend boundary is strong, but total separation is not
yet achieved.

The current schema-3 boundary report passes all eight checks with zero
violations. RouteDeck core has no Medusa or optional-adapter imports, the
framework constructs one operation runner and one navigation runner, FastAPI
derives every generic route from that runtime, Medusa owns all Store endpoints
and transport, the browser has no Store API path, and the optional LangGraph
adapter does not own product graph topology.

That automated pass has important blind spots. Manual source review found two
remaining cross-boundary control/copy problems, two session/configuration
problems that block a production multi-user claim, and several product or
framework maintenance duplications.

## Current Evidence

Commands run from the project root:

```powershell
python scripts/check_boundaries.py --json "$env:TEMP\routedeck-boundaries-20260720.json"
python -m ruff check routedeck_core routedeck_sqlalchemy routedeck_fastapi routedeck_langgraph examples/medusa-agent/backend/medusa_agent examples/medusa-agent/backend/main.py
pnpm --filter @routedeck/core typecheck
pnpm --filter @routedeck/react typecheck
pnpm --filter @routedeck/medusa-agent typecheck
```

Results:

- boundary report: schema 3, 8/8 checks passed, 0 violations;
- Ruff: all checked Python production paths passed;
- TypeScript: core, React, and Medusa frontend typechecks passed.

No service, database, Docker stack, real Medusa integration, live model, or
browser E2E was started. This audit does not claim a current checkout or
release pass.

## Finding Summary

| ID | Severity | Classification | Current finding |
| --- | --- | --- | --- |
| QB-01 | High | RouteDeck/consumer boundary | Medusa still owns a generic assistant-initiation stream and convergence state machine. |
| QB-02 | High | Framework session correctness | Review APIs accept an omitted session ID and fall back to one configured default session. |
| QB-03 | Medium | Framework/product copy boundary | Generic core/React conversation packages hardcode buyer-specific wording. |
| QB-04 | Medium | Adapter/security readiness | The current selector is one raw internal session ID in a guest cookie whose generic default is `secure=False`; authenticated multi-session resolution is absent. |
| QB-05 | Medium | Product integrity duplication | Checkout and orders independently implement the same contact fingerprint. |
| QB-06 | Medium | Product contract duplication | Backend surface schemas and frontend decoders are independently maintained without an executable parity gate. |
| QB-07 | Medium | Framework maintainability | Current-node lookup remains repeated across context, projection, navigation, and supervision. |
| QB-08 | Low | Product dead code/size | Two unused operation ID mirrors remain, and several production modules exceed 400 lines. |

## Detailed Findings

### QB-01 - Product-owned generic assistant stream coordination

`examples/medusa-agent/frontend/src/app/initialConversation.ts` is 305 lines
and independently owns generic RouteDeck protocol behavior:

- a fixed initial request identity and retry-ID construction;
- assistant stream event switching and request-ID validation;
- terminal-frame and duplicate-completion validation;
- RouteDeck version synchronization and conversation reload;
- conflict convergence through the RouteDeck event store;
- timeout, interruption, and outcome-unknown classification.

Medusa should own only the product decision to request a greeting when durable
conversation is empty and the product copy shown on failure. The reusable
assistant-turn coordinator belongs in `@routedeck/core` or the React
conversation package. The current implementation duplicates the same class of
conversation lifecycle that ADR-006 assigns to RouteDeck.

The former duplicate `ModelTurnPolicy` classifier is gone. One buyer model now
decides whether a legal tool is needed. QB-01 is the remaining frontend
conversation-boundary issue; it is not a parallel-tool-call problem.

### QB-02 - Optional session identity falls back to a default

`ReviewActionMixin.accept_review(...)` and `reject_review(...)` accept
`session_id: str | None` and select:

```python
target_session_id = session_id or self.default_session_id
```

The runtime therefore requires a `default_session_id`, and the Medusa host
hardcodes `"medusa-agent-default"`. FastAPI currently passes the guest cookie
session explicitly, so the reference HTTP path does not normally take the
fallback. The public runner contract still permits accidental cross-session
selection by any direct consumer that omits the argument.

That is incompatible with a fail-closed multi-user design. Review acceptance
and rejection should require an explicit already-authorized session identity.
The runner must not decide which user's session is intended.

### QB-03 - Buyer-specific copy leaks into generic packages

Nineteen production occurrences of `buyer`/`buyer-agent` remain in generic
framework paths:

- `packages/core/src/conversation/client.ts`;
- `packages/core/src/conversation/codec.ts`;
- `packages/react/src/conversation/useRouteDeckConversation.ts`;
- `routedeck_core/contracts/conversation.py`.

These are framework error messages and documentation strings, not Medusa
business behavior, but their wording assumes a buyer product. RouteDeck's
typed codes and generic public-safe messages should be product-neutral;
Medusa-owned UI may translate them into buyer-specific copy.

The existing boundary scanner looks for imports, Store paths, constructors,
topology mutation, and named fallback/test symbols. It does not scan generic
framework copy for product vocabulary, so this leak can coexist with a green
report.

### QB-04 - Guest cookie and deployment-policy hardcoding

The generic FastAPI adapter currently stores the internal RouteDeck
`session_id` directly in one HTTP-only guest cookie. It validates presence and
length but does not resolve an authenticated principal or authorize an opaque
consumer-facing session handle.

`GuestCookieSettings` defaults to:

```python
name = "routedeck_guest"
secure = False
path = "/"
```

The Medusa host does not override those settings. That is acceptable only
inside the explicitly local HTTP reference runtime; it is not production-safe
or multi-user proof. Cookie policy must be explicit at the host boundary, and
an authenticated adapter must resolve `(principal, opaque handle)` to an
authorized internal session ID before RouteDeck persistence is called.

Medusa also fixes local runtime policies in source: instance ID, 15-minute
review TTL, 24-hour resume TTL, default session ID, one worker, and two local
browser origins. These values are coherent for the protected single-process
demo, but they must become explicit deployment configuration before the
reference host can be presented as a reusable production composition.

### QB-05 - Contact fingerprint duplication

`features/checkout/models.py::_contact_fingerprint(...)` and
`features/orders/models.py::_order_contact_fingerprint(...)` independently
serialize email, shipping address, and billing address with the same canonical
JSON options and SHA-256 hash.

This is product-owned logic and does not belong in RouteDeck. It should be one
Medusa canonical function over one normalized contact value because drift can
make a valid completed order unverifiable or hide a meaningful contact change.

### QB-06 - Surface schema/decoder mirror

The backend correctly owns canonical strict `public_props_schema` declarations
for catalog, cart, checkout, and order surfaces. The Medusa frontend also
hand-maintains surface-specific decoders and repeated `exactKeys`/error
helpers.

Runtime browser validation is appropriate; independently maintaining the same
field, enum, and required-property meaning is the drift risk. Generate product
validators/types from the compiled contract or add a build-time parity gate
that runs server schemas and browser decoders over the same valid/invalid
fixtures.

### QB-07 - Repeated current-node lookup

Equivalent linear node lookup remains in at least:

- `routedeck_core/context/agent.py`;
- `routedeck_core/context/scope.py`;
- `routedeck_core/projection/projector.py`;
- `routedeck_core/navigation/engine.py`;
- `routedeck_core/navigation/transactions.py`;
- `routedeck_core/supervision/guards.py`;
- supervision outcome/review modules.

The variants disagree on missing-node behavior: some raise a typed runtime
error, some return `False`, and some leak `StopIteration`. A compiled immutable
node index/resolver should own lookup; caller-specific public error mapping can
remain at transport/navigation boundaries.

### QB-08 - Small dead mirror and large-module hotspots

`frontend/src/routedeck/identifiers.ts` still exports unused `catalog.list` and
`cart.open` constants. Product UI already resolves operations through declared
surface affordances, so the unused mirror should be deleted.

The audit also found multiple non-generated production modules above 400
lines, led by checkout models/providers, supervision outcome modules, the
SQLAlchemy store facade, navigation routes/transactions, and the LangGraph
driver. Size alone is not a defect; these are review and extraction hotspots.
Do not split them without a clear lifecycle or invariant owner.

## Hardcoding Classification

| Hardcoded value | Classification |
| --- | --- |
| Operation IDs, route templates, outcome names, strict schemas | Intentional product/framework contracts. |
| Pinned Medusa/npm/Docker versions and protected local smoke URLs | Intentional reproducible demo/release infrastructure. |
| Seed product records and public image URLs | Explicit demo fixture path, not a production data fallback. |
| Region, sales channel, payment provider, database URL, key, and live model | Correctly required from external configuration; no product-code ID default. |
| Test-only scripted graph | Acceptable: isolated behind `ROUTEDECK_MODEL_MODE=scripted-test-only` plus `ROUTEDECK_TEST_ONLY=1`. |
| Default review session selection | Problematic: hidden identity choice in a reusable runtime API. |
| `buyer-agent` framework messages | Problematic: product-specific copy in generic packages. |
| Guest cookie `secure=False` and local runtime policy constants | Local-demo-only; production/reuse blocker until made explicit. |

## Boundary Separation Status

| Boundary | Status | Evidence |
| --- | --- | --- |
| Core versus optional adapters/product | Strong | Core import scan passed across 80 files. |
| Runtime/runner/navigation ownership | Strong | One framework-built runner and navigation path; no product constructors. |
| Medusa Store transport and browser network | Strong | Store endpoint inventory and browser scan passed. |
| RouteDeck navgraph versus product LangGraph | Strong | Adapter topology scan passed; product owns graph creation. |
| Product feature composition | Strong | Four feature-owned declarations; composition contains no transition assembly. |
| Conversation frontend lifecycle | Not separated | QB-01. |
| Product-neutral framework copy | Not separated | QB-03. |
| Authenticated/multi-session selection | Not implemented | QB-02 and QB-04. |
| Product integrity/contract duplication | Partial | QB-05 and QB-06. |

## Recommended Next Steps

1. Add one framework-owned assistant-initiation coordinator and reduce Medusa
   bootstrap to the empty-conversation trigger plus product rendering/copy.
   Extend the boundary checker to reject product switches over generic
   assistant-stream event types.
2. Design and implement the explicit authenticated `SessionResolver` seam.
   Require an authorized session ID for review APIs, remove
   `default_session_id`, and make cookie/security/deployment policy explicit.
3. Replace buyer-specific framework wording with product-neutral typed errors;
   keep buyer copy in Medusa. Add a framework product-vocabulary scan.
4. Consolidate the Medusa contact fingerprint and add checkout-to-order
   equivalence proof over real typed values.
5. Add a compiled node index/resolver and migrate repeated lookup sites with
   one missing-node invariant.
6. Generate or parity-test product surface validators, then remove stale
   frontend operation constants and consolidate only clearly shared decoder/UI
   primitives.
7. Run targeted unit/type/boundary tests per slice. After those fixes, run the
   protected real-Medusa and live-model human checkout E2E once as the final
   behavior gate.

## Scanner Blind Spots To Close

The current green boundary report does not prove:

- absence of generic RouteDeck SSE state machines in product frontend code;
- absence of product vocabulary in generic framework messages;
- explicit session identity on every direct runner/review call;
- server-schema/browser-decoder parity;
- uniqueness of product-integrity algorithms;
- production cookie/deployment security.

Until those checks or equivalent tests exist, the report supports a strong
structural boundary claim, not a total-separation claim.
