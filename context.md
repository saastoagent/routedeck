# RouteDeck Context

Last updated: 2026-07-28
Status: M0 public source launch complete; repository-local wiki source and local
reader complete; registry package and GitHub Wiki publication pending.
RouteDeck is public at
[`github.com/saastoagent/routedeck`](https://github.com/saastoagent/routedeck),
and the first corrective GitHub Actions run is green. The protected local stack
is stopped. No PyPI or npm package publication is claimed.

## Start Here

1. [Critical prompt](./critical_prompt.md)
2. [ADR-006 runtime/conversation boundary](./decisions/ADR-006-framework-owned-runtime-and-conversation-boundary.md)
3. [RouteDeck reference](./docs/route-deck-reference.md)
4. [Feature and architecture coverage](./architecture/feature-coverage.md)
5. [Subsystem code map](./architecture/code-map.md)
6. [System flow index](./SYSTEM_FLOW_INDEX.md)
7. [Test index](./test_index/README.md)
8. [Latest checkpoint](./context_checkpoints/context_checkpoint_22-07-2026-wiki-mermaid.md)
9. [Public roadmap](./ROADMAP.md)
10. [Active coverage-hardening plan](./plans/2026-07-21-coverage-hardening.md)
11. [RouteDeck learning wiki](./wiki/Home.md)

ADR-006 controls runtime assembly and generic conversation. Non-superseded
ADR-005 controls named state and feature structure. ADR-004 controls scope,
product/framework separation, and local execution. Completed plans are
historical material under `docs/archive/`.

## Current Architecture

- Products author independently owned `Feature` modules with complete `Node`s.
  An `Application` selects features and an entry node; RouteDeck validates and
  compiles one immutable interaction graph.
- Exact `FeatureBindings` supply product handlers, providers, and guards.
  Missing, extra, duplicate, synchronous, or malformed ownership fails at
  startup.
- One `RouteDeckRuntime` owns canonical session, conversation, operation,
  review, navigation, surface, event, and projection state. One supervised
  runner governs application-semantic operations from agents and UI.
- FastAPI requires a host-owned session selector for both current-session
  authorization and request-aware created-session binding; principal, opaque
  handle, and guest policy remain host-owned. The optional LangGraph
  adapter drives product-supplied graphs without owning product topology,
  prompts, models, authentication, or business logic.
- `@routedeck/core` owns strict browser contracts and authoritative state;
  `@routedeck/react` supplies product-neutral UI primitives and the read-only
  Navgraph.
- Authenticated inspection can now include a driver-owned current model
  context and exact assembled system prompt. The LangGraph adapter derives it
  from the same default-deny context and prompt renderer used for model calls;
  products must explicitly declare the inspection base prompt.
- Once `RouteDeckBootstrapBoundary` has reached ready, later projection
  resync/reconnect phases keep the application mounted. Initial bootstrap,
  replacement, retained navigation, and terminal recovery remain gated.
- Headless assistant initiation now publishes accumulated, product-neutral
  presentation progress after every validated delta while preserving the same
  terminal proof, synchronization, conflict convergence, and canonical reload.
- Compiled node contracts now carry typed static conversation-input
  availability. React resolves it for the current node while consumers retain
  ownership of affected nodes and displayed wording.
- `RouteDeckSurfaceHost` now validates the complete consumer registry against
  the compiled frontend contract before rendering and reports missing or stale
  components as `surface_registry_mismatch`.

Medusa remains the reference consumer. It owns Store API transport, commerce
truth, product features, prompts/models/graphs, session policy, deployment,
and UI. RouteDeck owns only the reusable interaction-state and supervision
contracts. The browser never calls Medusa `/store/*` directly, and private IDs
and form values remain outside public/model state.

## M0 Publication State

- Public source launch commit:
  `7d71e4471778abdb5e44c7b642ac0e06227d1dbe` (`prepare RouteDeck public alpha`).
- CI correction commit:
  `6ec2d6d94009fdc1df98f2360b598775405d810c` (`fix first public CI bootstrap`).
- Canonical repository: `https://github.com/saastoagent/routedeck`.
- Repository-scoped commit email: `raghavdasila@saastoagent.com`.
- First green public CI run:
  `https://github.com/saastoagent/routedeck/actions/runs/29831749835`.
- Python and TypeScript CI jobs passed tests, lint/type checks, builds,
  architecture checks, and package/archive inspection.
- Local `artifacts/` evidence was intentionally excluded from publication.
- A repository-local 19-file learning wiki with a tested zero-key Hello World
  and 14 Mermaid diagrams is complete under `wiki/`. It has not been pushed to
  the separate GitHub Wiki repository.
- A local React reader for the checked-in wiki source is available through
  `pnpm wiki:dev`; pinned Mermaid 11.16.0 is lazy-loaded with strict security
  to render the checked-in diagrams without replacing the Markdown authority.
- PyPI and npm identities, trusted publishers, versions, and registry installs
  remain unproven and unpublished.

The exact publication record is in
[`logs/20260721_publication_and_ci_closeout.md`](./logs/20260721_publication_and_ci_closeout.md).
The completed implementation plan is archived at
[`docs/archive/2026-07-21-routedeck-public-alpha.md`](./docs/archive/2026-07-21-routedeck-public-alpha.md).

## Current Evidence

- The post-ready synchronization regression failed against the former boundary
  for `resync_required`, `resyncing`, and `connecting`, then passed after the
  fix. The full React package passed 18 tests, strict typecheck, and build. A
  rebuilt Corpus browser run held the Lounge for 150/150 samples over 15
  seconds with zero loading transitions and zero console warnings/errors;
  the pre-fix run switched 33 times in six seconds.
- The request-aware created-session selector change passed all 25 FastAPI
  tests and focused Ruff checks. The Corpus consumer passed 63 backend and 23
  frontend tests, strict typecheck/build, and a rebuilt local browser run whose
  expired owner route recovered through `410 -> 201 -> event stream 200` to the
  Lounge without exposing framework expiry copy.
- The 2026-07-28 contract-boundary regression passed 520 non-real Python tests,
  all root package tests (47 core, 15 React, 15 testing, 71 Medusa frontend,
  and 5 wiki), root typecheck, and root build. The four protected real-Medusa
  tests remain a separate live-stack gate and were not needed for this change.
- Agent-context inspection passed 84 focused FastAPI/LangGraph tests, 88 core
  tests, 18 React tests, Ruff, strict typechecks, generated-contract drift, and
  package builds. The broader Python run passed 518/520; its two unrelated
  failures remain stale server-owned-conversation/public-export expectations,
  including one fixture imported from the older `agent-core` checkout.

- Wiki closeout: 19 Markdown files, 1,208 lines, 14 Mermaid diagrams, one
  focused Hello World test passed, 618/618 live files mapped, and 63 active
  Markdown files passed the context/link check. Full evidence is in
  [`logs/20260722_route_deck_wiki_closeout.md`](./logs/20260722_route_deck_wiki_closeout.md).
- Local wiki reader and Mermaid renderer: 5 focused tests passed, strict
  TypeScript typecheck passed, the production build passed, the dependency
  audit found no known vulnerabilities, and documentation coverage mapped
  634/634 live files. Live browser
  checks rendered flowchart, sequence, and state SVGs, opened the Mermaid
  source disclosure, reported no render alerts or warning/error console
  entries, and preserved zero horizontal overflow at 390 px. The smoke URL is
  `http://127.0.0.1:5176/?page=Architecture`.
- Public GitHub Actions run `29831749835`: completed successfully for commit
  `6ec2d6d94009fdc1df98f2360b598775405d810c`.
- Pre-publication clean regression: 513 non-live Python tests and 122
  TypeScript tests passed after coverage hardening.
- The 2026-07-22 assistant-progress slice passed 36/36 headless core tests,
  core typecheck/build, and a gated test proving partial text is observable
  before durable completion. These source changes are not published to npm.
- Clean Python state coverage: 200/200 statements and 48/48 branches across 49
  focused tests.
- `RouteDeckObservableState`: 100% statements, branches, functions, and lines
  across 10 focused tests.
- Built Python and npm archives passed isolated consumer installation and
  import/build verification before publication.
- Latest protected live checkout evidence remains the dated 2026-07-20 run:
  1 passed in 2.2 minutes using the live model and real Store API. Its video is
  local release evidence and is not in the public checkout.

Only these named runs support pass claims. The protected stack must not be
assumed running in a later session.

## Known Gaps And Next Step

- The active coverage-hardening plan still needs high-value Python and
  TypeScript gap closure plus baseline-and-ratchet CI thresholds.
- The developer's global Python environment still contains an editable
  `routedeck-core` entry for the older `agent-core` checkout. Coverage evidence
  must use an isolated environment until that external environment is repaired.
- Publishing the checked-in `wiki/` source to the separate GitHub Wiki
  repository requires explicit authorization for git operations.
- A production principal-aware selector example is not implemented. Identity
  policy remains consumer-owned.
- Private-form save/resync latency needs instrumentation before any performance
  change. Redundant model confirmation remains Medusa variability unless a
  trace proves a RouteDeck transition defect.
- PyPI/npm namespace ownership and trusted-publisher configuration require
  external account actions. A registry release must be verified by installing
  the published artifacts, not the local candidates.
- The protected reset/full release harness remains separately approval-gated.

The immediate release step is to establish PyPI/npm package ownership and
trusted publishers, choose the first alpha versions, publish, and verify clean
registry installs. M1 agent-native authoring begins after that M0 package
release. Coverage hardening may continue independently without expanding
framework scope.

## Maintenance Contract

`architecture/feature-coverage.md` owns capability coverage;
`architecture/code-map.md` owns subsystem/source mapping;
`knowledgebase/runtime-boundary-implementation-coverage.md` owns the reusable
cross-owner semantic trace; `test_index/README.md` owns validation meaning.
After material work, follow `work_prompt.md`: archive the prior context when
needed, add a log and checkpoint, rewrite this snapshot, and run
`python scripts/check_doc_coverage.py` plus
`python scripts/check_context_architecture.py`.
