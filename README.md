# RouteDeck

Start with `docs/agentic-ui-state-runtime.md` for the current architecture direction.

RouteDeck is a full-stack framework for robust agentic applications, with an
embeddable state and interaction runtime for existing agents.

Full Flow applications import RouteDeck, declare domain state, flows,
operations, guards, handlers, context, and surfaces, then let RouteDeck compile
and run the LangGraph-backed backend plus typed event/SSE, projection,
diagnostics, and React state path. Core Integration applications attach an
existing agent or custom graph to the same state and interaction kernel through
an executor adapter.

RouteDeck defines how agent-centric platforms expose graph state, valid actions,
blocked actions, recovery prompts, forms, runtime snapshots, surface state,
streaming events, and debugger/authoring UI. RouteDeck can provide direct
adapters for LangGraph, FastAPI, and React, but product behavior stays in the
consuming application.

Downstream applications import RouteDeck as their agentic app state layer. The
product owns conversation behavior, domain APIs, surface copy, recovery wording,
and public chat behavior. RouteDeck owns the generic state management contract
that lets those product decisions travel from graph/backend execution into
React.

It is split into:

- `routedeck_core`: Python contracts, projections, operations, events, surfaces, runtime state, and validation helpers for backend agentic state.
- `routedeck_langgraph`: first-class Full Flow execution compiler and custom LangGraph adapter; the current implementation contains the validation and graph-wiring foundation.
- planned `routedeck_sqlite`: durable single-host session, idempotency, event-log, replay, and transactional outbox backend.
- planned `routedeck_fastapi`: product-neutral contract/session/dispatch/review/inspect routes and typed SSE channel transport.
- planned `routedeck_testing`: shared Full Flow/Core Integration conformance harness.
- `react`: React store, hooks, debugger, and type contracts for frontend agentic state consumers.
- `architecture`: code-referenced subsystem ownership, component contracts, and maintenance coverage.
- `docs`: framework-level architecture and packaging notes.
- `examples/medusa-agent`: product reference integration used to prove RouteDeck can power a real product agent without absorbing product behavior.
- planned `examples/full-flow-change-planner` and `examples/core-integration-document-review`, both independent of Corpus/Medusa.
- `skills`: repo-local skills and scaffolding helpers for creating manifests and wiring RouteDeck into graph runtimes.
- root context files: RouteDeck-local context, handoff, validation index, and lifecycle anchors populated from the sibling `context_architecture_bundle` starter.

`docs/medusa-agent-reference-app.md` is the active source-of-truth spec for a
product-specific Medusa reference app. `examples/medusa-agent` is the active
runnable example and must stay chat-first while RouteDeck behavior is
introduced underneath it in disciplined slices.
`docs/propertydesk-reference-app.md` is retained only as superseded planning
context.

The framework is a sibling local package during development. Downstream
applications should consume `routedeck-core`, `routedeck-langgraph`, and
`@routedeck/react` from this folder instead of copying framework source.

## Developer Modes

- **Full Flow:** RouteDeck supplies the LangGraph-native full-stack golden path
  for ordinary developers and agent-assisted/vibe coding.
- **Core Integration:** RouteDeck supplies state and interaction management for
  an existing agent or custom graph without requiring an execution rewrite.

Both modes share operations, guards, review, events, projections, surfaces,
diagnostics, and React store semantics. See
`decisions/ADR-002-two-adoption-modes-one-kernel.md`.

One application specification drives public nodes, flows/outcomes, operations,
surface identity/placement, declared event schemas, validation, and the exported
frontend contract. RouteDeck atomically claims dispatch before execution and
ships a durable SQLite reference backend; it does not silently claim exactly-once
side effects across external systems.

## LangGraph Runtime

`routedeck_core` keeps framework-neutral contracts dependency-light. LangGraph
is the first-class Python execution foundation; install the LangGraph extra for
Full Flow and custom LangGraph integrations:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[langgraph]"
```

The adapter exposes:

- `validate_langgraph_contract(...)`
- `assert_route_transition(...)`
- `build_route_deck_state_graph(...)`

Use it when LangGraph should execute the flow while RouteDeck remains the
application state contract exposed to backend services and React.

## Repo-Local Skills

RouteDeck includes repo-local skills for repeatable integration work:

- `skills/routedeck-manifest-authoring`: design or repair a RouteDeck manifest from real runtime stages.
- `skills/routedeck-manifest-scaffolder`: generate a starter Python manifest module from a JSON flow spec.
- `skills/routedeck-langgraph-integration`: wire RouteDeck snapshots and action submission around a LangGraph-style backend.

The context architecture starter kit includes its own copyable skills:

- `context_architecture_bundle/skills/create-context-architecture-bundle`: create a complete context architecture bundle from a project idea or spec.
- `context_architecture_bundle/skills/populate-context-architecture`: populate or repair context architecture for an existing codebase.

To scaffold a starter manifest module:

```powershell
python skills/routedeck-manifest-scaffolder/scripts/scaffold_manifest.py skills/routedeck-manifest-scaffolder/examples/basic-flow.json generated_manifest.py --force
```

The generated module exposes `MANIFEST`, `MANIFEST_VALIDATION_ERRORS`, `manifest()`, and `manifest_json()`. Treat it as a starting contract, then add app-level parity tests that every visible node/action maps to executable runtime behavior.

## Architecture Coverage

Use `architecture/code-map.md` before changing RouteDeck source, examples,
packaging, or repo-local skills. It maps subsystems to source globs,
architecture anchors, test anchors, and update triggers.

Run the advisory checker before closeout:

```powershell
python scripts/check_doc_coverage.py
```
