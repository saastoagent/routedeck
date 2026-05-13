# Minimal LangGraph Adapter Example

This example shows RouteDeck as the visible navigation contract and LangGraph as the executable runtime.

Run from the `routedeck` folder:

```powershell
python examples/minimal-langgraph-adapter/app.py
```

The example demonstrates:

- `routedeck_core` manifest models.
- `routedeck_langgraph.validate_langgraph_contract`.
- `routedeck_langgraph.build_route_deck_state_graph`.
- `routedeck_langgraph.assert_route_transition`.
- RouteDeck runtime snapshot output that a React debugger can render.
