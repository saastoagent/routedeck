# LangGraph Adapter

## Purpose

This component owns the optional LangGraph bridge. It lets a product keep
LangGraph as the execution engine while RouteDeck remains the state, manifest,
transition, and UI contract.

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

## Dependent Flows

- Validation-only integrations with existing LangGraph apps.
- RouteDeck-style graph builder integrations.
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
