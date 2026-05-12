# RouteDeck

RouteDeck is an agentic navigation UX framework for LangGraph/FastAPI/React-style applications.

It defines how agent-centric platforms expose navigable graph state, valid actions, blocked actions, recovery prompts, forms, runtime snapshots, and debugger/authoring UI. RouteDeck can provide direct adapters for LangGraph, FastAPI, and React, but product behavior stays in the consuming application.

It is split into:

- `routedeck_core`: Python contracts and validation helpers for backend runtimes that sit above LangGraph/FastAPI.
- `react`: React debugger and type contracts for frontend shells.
- `docs`: framework-level architecture and packaging notes.
- `examples/minimal-fastapi-react`: minimal working example showing the full contract without SaaStoAgent product code.
- `skills`: repo-local skills and scaffolding helpers for creating manifests and wiring RouteDeck into graph runtimes.

The framework is a sibling local package during development. SaaStoAgent consumes `routedeck-core` and `@routedeck/react` from this folder instead of copying framework source into the SaaStoAgent project.

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
