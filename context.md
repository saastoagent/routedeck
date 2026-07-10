# RouteDeck Context

Last updated: 2026-07-10 08:51 IST
Status: Full-stack framework direction and two adoption modes are locked; the
implementation is a partial runtime foundation and the full refactor is the
active next goal.

## Start Here

1. `critical_prompt.md`
2. `context.md`
3. `context_checkpoints/context_checkpoint_10-07-2026-08-51AM.md`
4. `docs/route-deck-reference.md`
5. `decisions/ADR-001-langgraph-native-routedeck.md`
6. `decisions/ADR-002-two-adoption-modes-one-kernel.md`
7. `docs/superpowers/plans/2026-07-10-routedeck-full-stack-framework-refactor.md`
8. `architecture/code-map.md`
9. `test_index/README.md`

## Locked Product Direction

RouteDeck is the full-stack framework for robust agentic applications. It sits
on top of LangGraph for the default Python execution path and makes it easy to
build predictable agentic products with typed operations, guards, review,
dynamic surfaces, typed events, SSE, projections, diagnostics, and React state.

RouteDeck supports two developer journeys through one kernel:

1. **Full Flow:** ordinary developers and agent-assisted/vibe coders declare an
   application; RouteDeck compiles and runs the LangGraph backend plus the
   event/SSE/projection/React path.
2. **Core Integration:** advanced developers keep an existing agent or custom
   graph and attach it to RouteDeck state and interaction management through a
   typed executor adapter.

Full Flow and Core Integration must share operation, guard, review, event,
projection, surface, store, and diagnostics semantics. LangGraph is the
first-class execution foundation; custom LangGraph graphs remain first-class.

One application specification is authoritative for public nodes, flows/outcomes,
operations, surface identity/placement, affordances, declared event schemas, and
the versioned frontend contract. Dispatch is claimed before executor side
effects. The target includes a durable transactional SQLite reference backend;
external exactly-once behavior is never implied when a downstream system does
not participate in the transaction.

## Event Architecture

RouteDeck owns one typed event protocol with explicit semantic channels:

- `assistant`
- `runtime`
- `tool`
- `surface`
- `diagnostic`

Events share identity, run/turn correlation, sequence ordering, projection
version, timestamp, visibility, terminal semantics, and replay rules. Products
may expose filtered SSE endpoints or a multiplexed endpoint, but public
assistant consumers must never receive private diagnostics, credentials, raw
graph state, or hidden route operations.

## Current Implementation Reality

Already present:

- product-neutral Python contracts and validation
- `RouteDeckRuntimeBase` with dispatch, projection, navigation, surface, review,
  and event helpers
- `RouteDeckApp` builder foundation
- `routedeck_langgraph` validation and common graph wiring
- `@routedeck/react` store, provider, hooks, surfaces, and debugger
- Medusa product reference example
- SaaStoAgent/Corpus consuming RouteDeck contracts directly in the committed
  boundary checkpoint `189a6559`

Not yet present at the required framework level:

- a complete declarative Full Flow application specification and compiler
- actual Corpus execution through that RouteDeck/LangGraph compiler
- a production Core Integration executor contract and conformance suite
- the complete shared event envelope, channel filtering, replay, and SSE runtime
- a durable coordinated session/event/outbox backend
- generated/shared backend-to-frontend application contracts
- a lightweight Corpus without generic projection/event/runtime assembly
- standalone Full Flow and Core Integration examples independent of Corpus

## Required Standalone Examples

Framework readiness requires:

1. `examples/full-flow-change-planner/`: a self-contained real
   LangGraph-backed app compiled by RouteDeck, with backend, SSE, React surfaces,
   tests, and smoke commands.
2. `examples/core-integration-document-review/`: a self-contained existing
   LangGraph agent adapted to RouteDeck state, operations, events, projections,
   and React without rewriting the execution topology.

Neither example may depend on Corpus, SaaStoAgent models, private credentials,
or fake product data. Test fixtures must remain isolated to tests.

## Validation And Completion Standard

The refactor must add and pass:

- core specification/compiler contract tests
- Full Flow and Core Integration conformance tests
- LangGraph/custom-graph integration tests
- event ordering, visibility, terminal, reconnect, and replay tests
- dispatch-claim, interruption, process-reopen, and atomic outbox tests
- projection/operation/guard/review regression tests
- React store/event reducer/surface-host tests
- per-example backend and frontend tests
- clean-install and smoke tests for both examples
- Corpus regression and browser acceptance tests

A new Corpus-like app must not need to copy a product runtime subclass,
projection assembly, navigation mechanics, event sequencing, or SSE formatting.

## Current Validation Snapshot

The committed Corpus checkpoint was validated with Python 3.12 compilation, 32
dependency-free source-boundary checks, and the previously documented Mac mini
Tailscale runtime/browser smoke. No services were started for this context
closeout, and the full RouteDeck suite was not rerun locally.

For this architecture closeout, both documentation coverage scripts exited `0`,
all `13` dependency-free RouteDeck reference guards passed, `39` changed/new
Markdown files had `0` missing relative links, and the scoped whitespace check
passed. Coverage warnings were advisory context-anchor notices; no runtime source
changed.

## Medusa Reference Guard

The Medusa reference example remains the current product-owned reference while
the two standalone adoption examples are built. Preserve the **2026-06-10 gap audit**
and its **chat-to-projection convergence** requirement: assistant prose
is not accepted as a state change unless the same product request crosses the
runtime boundary and produces the matching projection update. This closeout did
not change Medusa runtime behavior or its focused test contract.

## Next Goal

Execute
`docs/superpowers/plans/2026-07-10-routedeck-full-stack-framework-refactor.md`
task by task with test-first slices and meaningful commits. Preserve framework
purity, fail loudly on missing dependencies, and keep unrelated research work
out of RouteDeck commits.

## Context Architecture Closeout

- Log: `logs/20260710_0851_full_stack_framework_goal.md`
- Checkpoint: `context_checkpoints/context_checkpoint_10-07-2026-08-51AM.md`
- Archived context:
  `context_history/20260710_context_before_full_stack_framework_goal.md`
- Decisions: `ADR-001` and `ADR-002`

Before runtime/browser verification, ask whether to use local, Mac mini LAN, or
Mac mini Tailscale and report the exact command and smoke URL.
