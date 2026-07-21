# RouteDeck Context

Last updated: 2026-07-21
Status: M0 public source launch complete; registry package release pending.
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
8. [Latest checkpoint](./context_checkpoints/context_checkpoint_21-07-2026-publication-and-ci.md)
9. [Public roadmap](./ROADMAP.md)
10. [Active coverage-hardening plan](./plans/2026-07-21-coverage-hardening.md)

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
- FastAPI requires a host-owned session selector. The optional LangGraph
  adapter drives product-supplied graphs without owning product topology,
  prompts, models, authentication, or business logic.
- `@routedeck/core` owns strict browser contracts and authoritative state;
  `@routedeck/react` supplies product-neutral UI primitives and the read-only
  Navgraph.

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
- PyPI and npm identities, trusted publishers, versions, and registry installs
  remain unproven and unpublished.

The exact publication record is in
[`logs/20260721_publication_and_ci_closeout.md`](./logs/20260721_publication_and_ci_closeout.md).
The completed implementation plan is archived at
[`docs/archive/2026-07-21-routedeck-public-alpha.md`](./docs/archive/2026-07-21-routedeck-public-alpha.md).

## Current Evidence

- Public GitHub Actions run `29831749835`: completed successfully for commit
  `6ec2d6d94009fdc1df98f2360b598775405d810c`.
- Pre-publication clean regression: 513 non-live Python tests and 122
  TypeScript tests passed after coverage hardening.
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
