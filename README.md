# RouteDeck

Start with `docs/agentic-ui-state-runtime.md` for the current architecture direction.

RouteDeck is graph-backed state management for agentic applications.

Applications should import RouteDeck and use it the way frontend apps use Redux,
MobX, or React Query: as a reusable state layer, not as product code. On the
backend, RouteDeck binds LangGraph/FastAPI runtime state into a stable agentic
state contract. On the frontend, `@routedeck/react` exposes that contract through
stores, hooks, surfaces, events, and debugger components.

RouteDeck defines how agent-centric platforms expose graph state, valid actions,
blocked actions, recovery prompts, forms, runtime snapshots, surface state,
streaming events, and debugger/authoring UI. RouteDeck can provide direct
adapters for LangGraph, FastAPI, and React, but product behavior stays in the
consuming application.

For example, Corpus should import and use RouteDeck as SaaStoAgent's agentic app
state layer. Corpus owns SaaStoAgent-specific conversation, setup behavior,
surface copy, recovery wording, and public chat behavior. RouteDeck owns the
generic state management contract that lets those product decisions travel from
LangGraph/backend execution into React.

It is split into:

- `routedeck_core`: Python contracts, projections, operations, events, surfaces, runtime state, and validation helpers for backend agentic state.
- `routedeck_langgraph`: optional LangGraph adapter for handler parity, edge resolver validation, transition assertions, and common graph wiring.
- `react`: React store, hooks, debugger, and type contracts for frontend agentic state consumers.
- `docs`: framework-level architecture and packaging notes.
- `examples/minimal-langgraph-adapter`: minimal backend-only LangGraph adapter example.
- `examples/minimal-fastapi-react`: minimal working example showing the full contract without SaaStoAgent product code.
- `skills`: repo-local skills and scaffolding helpers for creating manifests and wiring RouteDeck into graph runtimes.

The framework is a sibling local package during development. SaaStoAgent consumes `routedeck-core`, `routedeck-langgraph`, and `@routedeck/react` from this folder instead of copying framework source into the SaaStoAgent project.

## LangGraph Adapter

`routedeck_core` stays runtime-neutral and dependency-light. Install the optional LangGraph extra only for LangGraph apps:

```powershell
pip install -e ".[langgraph]"
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

To scaffold a starter manifest module:

```powershell
python skills/routedeck-manifest-scaffolder/scripts/scaffold_manifest.py skills/routedeck-manifest-scaffolder/examples/basic-flow.json generated_manifest.py --force
```

The generated module exposes `MANIFEST`, `MANIFEST_VALIDATION_ERRORS`, `manifest()`, and `manifest_json()`. Treat it as a starting contract, then add app-level parity tests that every visible node/action maps to executable runtime behavior.
