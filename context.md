# RouteDeck Context

Last updated: 2026-07-21
Status: M0 public-alpha publication is active. The current runtime remains
proven by the dated evidence below; the protected stack is stopped. Boundary 1
has repaired release-contract drift, added the public roadmap/project contract,
and established clean artifact and non-destructive CI paths. No public release,
registry package, Git operation, protected reset, or external namespace setup
is claimed.

## Start Here

1. [Critical prompt](./critical_prompt.md)
2. [ADR-006 runtime/conversation boundary](./decisions/ADR-006-framework-owned-runtime-and-conversation-boundary.md)
3. [RouteDeck reference](./docs/route-deck-reference.md)
4. [Feature and architecture coverage](./architecture/feature-coverage.md)
5. [Subsystem code map](./architecture/code-map.md)
6. [System flow index](./SYSTEM_FLOW_INDEX.md)
7. [Test index](./test_index/README.md)
8. [Post-fix quality and boundary audit](./audits/2026-07-20-routedeck-quality-boundary-post-fix-audit.md)
9. [Implementation coverage crosswalk](./knowledgebase/runtime-boundary-implementation-coverage.md)
10. [Latest checkpoint](./context_checkpoints/context_checkpoint_20-07-2026-5-20PM.md)
11. [Public roadmap](./ROADMAP.md)
12. [Active public-alpha plan](./plans/2026-07-21-routedeck-public-alpha.md)
13. [Active coverage-hardening plan](./plans/2026-07-21-coverage-hardening.md)

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

## Implementation Coverage

- ADR-006 records the implemented framework runtime, required session-selector,
  assistant-turn coordinator, and schema-4 enforcement boundary.
- ADR-005 records implemented feature/node composition, immutable compiled node
  lookup, explicit review identity, and read-only Navgraph behavior.
- ADR-004 records the implemented Medusa commerce, deployment-policy, contact
  identity, surface parity, and browser/Store separation.
- `architecture/feature-coverage.md` remains the canonical capability matrix;
  `architecture/code-map.md` maps every maintained file to an owner.
- `knowledgebase/runtime-boundary-implementation-coverage.md` is the single
  verified cross-owner file/contract/proof trace. It is evidence subordinate to
  the ADRs, canonical docs, and current source.

## Current Evidence

- Coverage hardening checkpoint: a clean temporary Python environment installed
  from this standalone checkout collected the maintained suite without the old
  `agent-core` editable checkout. The Python state subsystem reached 100%
  statement and branch coverage (200/200 statements, 48/48 branches; 49 focused
  tests), and `RouteDeckObservableState` reached 100% statements, branches,
  functions, and lines (44/44, 45/45, 21/21, 40/40; 10 focused tests). The full
  clean non-live Python regression passed 513 tests. This is an in-progress
  checkpoint, not a claim of repository-wide 100% coverage.

- M0 Boundary 1 verification: 500 non-live Python tests passed; clean mypy
  found no issues in 224 source files; 114 TypeScript tests passed; workspace
  typecheck/build passed; boundary schema 4 passed with zero violations; and
  documentation mapped 596/596 live files. Exact commands and caveats are in
  `logs/2026-07-21-public-alpha-boundary-1.md`.
- Fresh candidate artifacts under
  `C:\Users\ragha\AppData\Local\Temp\routedeck-m0-final-20260721` passed archive
  inspection and isolated Python/npm consumer checks. These are local
  artifacts, not registry releases.

- Schema-4 boundary report: pass, zero violations at
  `C:\Users\ragha\AppData\Local\Temp\routedeck-boundaries-docs-final.json`.
- Documentation coverage: 574/574 maintained files mapped; context architecture
  passes for 41 active Markdown files.
- Focused authority/public/reference lane: 29 passed with one existing Pydantic
  deprecation warning.
- Maintained Python Ruff and core/React/Medusa TypeScript typechecks pass.
- Focused tests for assistant coordination, explicit review session identity,
  selector/host policy, neutral copy/scanners, contact identity, compiled node
  lookup, and surface parity pass.
- Real Medusa integration: 4 passed in 21.131 seconds against
  `http://127.0.0.1:9100`.
- Latest live checkout: 1 passed in 2.2 minutes at `http://127.0.0.1:5198`, using the
  live model and real Store API. The uninterrupted 1920x1080 video is
  [video.webm](./artifacts/boundary-quality-live-checkout-20260720-165922/raw-results/human-checkout-flow--human-7f281-th-visible-navigation-proof-desktop-chromium/video.webm).

Only these named current runs support pass claims. The protected stack should
not be assumed running in a later session.

## Known Gaps And Next Step

- Repository-wide 100% executable coverage is intentionally not an M0 launch
  requirement. Continue the coverage-hardening plan as a baseline-and-ratchet
  effort, prioritizing critical failure and recovery semantics without delaying
  the usable alpha for exhaustive line execution.
- The developer's global Python environment contains an editable
  `routedeck-core` entry for the older `agent-core` checkout. Coverage and
  collection evidence must use the clean temporary environment or another
  isolated install until that external environment is intentionally repaired.

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
- Public release remains unclaimed until the explicitly authorized protected
  harness, external namespace/trusted-publisher setup, Git release work, and
  registry publication each produce current evidence.

The immediate next step is to finish Boundary 1's non-destructive verification
record, then stop for approval. The following gates remain outside Boundary 1:
Git operations, repository visibility, package-name reservation, trusted
publisher configuration, the protected demo reset/full release harness, and
PyPI/npm publication. M1 feature work begins only after the M0 alpha is released.

## Maintenance Contract

`architecture/feature-coverage.md` owns capability coverage;
`architecture/code-map.md` owns subsystem/source mapping;
`knowledgebase/runtime-boundary-implementation-coverage.md` owns the reusable
cross-owner semantic trace; `test_index/README.md` owns validation meaning. Run
`python scripts/check_doc_coverage.py` and
`python scripts/check_context_architecture.py` after changing these surfaces.
Archive completed plans/designs so historical material cannot compete with
current authority.
