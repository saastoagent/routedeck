# RouteDeck Framework Architecture

> Canonical direction: read `docs/agentic-ui-state-runtime.md` first. RouteDeck is graph-backed state management for agentic UI. This document describes the older package split and should be interpreted through that runtime/store model.

RouteDeck is a framework layer for agentic navigation UX. It is not a replacement for LangGraph, FastAPI, or React.

RouteDeck owns the contract and reusable UI for graph navigation: manifest shape, runtime snapshot shape, valid and blocked action surfaces, recovery prompts, forms, graph debugging, and future authoring surfaces. Product applications own domain graph behavior, auth, workspace semantics, and business decisions.

## Backend Package

`routedeck_core` is the backend package. It should stay free of SaaStoAgent database models, auth models, and product handlers.

It provides:

- Pydantic contracts for manifests, nodes, edges, actions, fields, policies, and runtime snapshots.
- Manifest validation.
- Runtime snapshot helpers.

In a LangGraph/FastAPI app, the normal layering is:

1. LangGraph executes state transitions.
2. Product stage handlers perform domain work.
3. RouteDeck validates submitted UI actions and emits manifest/snapshot metadata.
4. FastAPI transports the manifest, actions, and snapshots over REST/SSE.

SaaStoAgent-specific files under `backend/services/route_deck/` are an adapter/catalog on top of `routedeck_core`.

Stack-specific helpers for LangGraph or FastAPI can live in RouteDeck as adapters, but they must stay product-neutral.

## LangGraph Adapter

`routedeck_langgraph` is the optional bridge for LangGraph apps. It owns the LangGraph dependency and provides:

- Manifest-to-handler parity validation.
- Edge condition resolver validation.
- Transition assertions that verify handler output stays on RouteDeck edges.
- A common `StateGraph` builder for apps that want RouteDeck-style grouped graph wiring.

Use the adapter in two levels:

1. Validation-only: keep an existing LangGraph graph and call `validate_langgraph_contract(...)` plus `assert_route_transition(...)`.
2. Graph-builder: call `build_route_deck_state_graph(...)` to scaffold the common `turn_start -> route_action -> group -> node -> finalize` wiring.

Do not put product-specific auth, workspace, or persistence logic into the adapter.

## Frontend Package

`@routedeck/react` is the frontend package. It should stay free of SaaStoAgent store, auth, routes, and domain components.

It provides:

- Shared TypeScript contracts for RouteDeck manifests and runtime snapshots.
- Debugger components that visualize nodes, edges, valid actions, blocked actions, and recovery prompts.
- A full-graph canvas that sizes from the manifest instead of assuming a fixed app-specific node count. Product shells can place it in a drawer, modal, or standalone debug page.

In a React app, the normal layering is:

1. Product shell owns layout, routing, auth, and state store.
2. Product API client stores RouteDeck manifest/snapshot payloads.
3. `@routedeck/react` renders reusable debugging or authoring surfaces.
