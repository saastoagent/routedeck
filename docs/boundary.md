# RouteDeck Boundary

RouteDeck owns agentic navigation UX contracts.

It owns:

- manifest and runtime snapshot schemas
- validation helpers for graph navigation payloads
- valid and blocked action surfaces
- recovery prompt and form metadata contracts
- reusable React debugger and future authoring UI
- optional product-neutral adapters for LangGraph, FastAPI, and React
- runnable examples and package docs

Consuming products own:

- domain graph catalogs and node/action IDs
- auth, workspace, account, and persistence semantics
- business workflow handlers
- REST tool execution decisions
- product shell layout, routing, state, and visual identity

For SaaStoAgent, `backend/services/route_deck/` remains the product adapter/catalog. It imports RouteDeck primitives from `routedeck_core`, uses `routedeck_langgraph` for LangGraph contract checks and transition assertions, and passes RouteDeck snapshots to the SaaStoAgent frontend, which renders framework UI through `@routedeck/react`.

`routedeck_core` must not import LangGraph. LangGraph support lives in the optional `routedeck_langgraph` adapter so non-LangGraph runtimes can still use RouteDeck manifests and snapshots.
