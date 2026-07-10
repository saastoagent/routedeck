# LangGraph Adapter

## Purpose

This component owns RouteDeck's first-class LangGraph execution path. It
compiles Full Flow application definitions into the standard LangGraph runtime
shape and lets advanced developers attach an existing custom LangGraph graph
without rewriting it. RouteDeck remains the interaction, state, event,
projection, surface, diagnostics, and UI contract.

The Full Flow compiler produces only domain execution/outcome mapping behind the
executor protocol. It must not duplicate the shared kernel's session loading,
guards, review, dispatch claim, commit, projection, or terminal event behavior.
For Core Integration, the existing graph checkpointer remains authoritative for
private executor state while RouteDeck remains authoritative for public
interaction-session state and projection.

## Owner Files

- `routedeck_langgraph/graph.py`
- `routedeck_langgraph/transition.py`
- `routedeck_langgraph/types.py`
- `routedeck_langgraph/validation.py`
- `routedeck_langgraph/__init__.py`

## Public Interfaces

- `validate_langgraph_contract(...)`
- `assert_route_transition(...)`
- `build_route_deck_state_graph(...)`
- Transition assertion and condition resolver contracts.
- Planned Full Flow compiler from a validated RouteDeck application definition.
- Planned custom-graph executor adapter that maps snapshot, dispatch, and stream
  behavior into the shared RouteDeck runtime.
- Explicit reconciliation contract for private-checkpoint success followed by
  public RouteDeck commit interruption; retry never silently reruns the graph.

## Dependent Flows

- Full Flow applications compiled and run by RouteDeck.
- Existing/custom LangGraph applications using Core Integration.
- Product graph parity checks before exposing operations to UI/agents.

## Tests And Evidence

- `tests/test_langgraph_adapter.py`
- `python -m pytest tests/test_langgraph_adapter.py -q`

## Update Triggers

Update this doc and `architecture/code-map.md` when changing:

- LangGraph dependency assumptions
- graph builder topology
- handler parity rules
- transition assertion behavior
- condition resolver policy
- adapter public exports

The adapter must stay product-neutral. Product auth, workspace, persistence,
prompts, and domain execution belong in the consuming application.

LangGraph implementation types should not leak into framework-neutral
projection, operation, surface, event, or React contracts. Full Flow and custom
graph integrations must pass the same RouteDeck conformance suite.
