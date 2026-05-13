from __future__ import annotations

from collections.abc import Callable
from typing import Any, Mapping

from routedeck_core import RouteDeckManifest

from .types import GroupMap, HandlerMap
from .validation import validate_langgraph_contract


def _normalize_groups(manifest: RouteDeckManifest, groups: GroupMap | None) -> dict[str, set[str]]:
    if groups:
        return {group_id: set(nodes) for group_id, nodes in groups.items()}
    return {"route_deck": {node.id for node in manifest.nodes}}


def _default_active_node(state: Mapping[str, Any], fallback: str) -> str:
    return str(state.get("active_stage_id") or state.get("node") or fallback)


def build_route_deck_state_graph(
    *,
    manifest: RouteDeckManifest,
    state_schema: Any,
    handlers: HandlerMap,
    condition_resolvers: Mapping[str, Callable[..., bool]],
    groups: GroupMap | None = None,
    active_node_resolver: Callable[[Mapping[str, Any]], str] | None = None,
    turn_start_node: Callable[[Any], Any] | None = None,
    route_action_node: Callable[[Any], Any] | None = None,
    finalize_node: Callable[[Any], Any] | None = None,
    entry_node_name: str = "turn_start",
    route_action_node_name: str = "route_action",
    finalize_node_name: str = "finalize_turn",
):
    from langgraph.graph import END, StateGraph

    normalized_groups = _normalize_groups(manifest, groups)
    errors = validate_langgraph_contract(
        manifest,
        handlers,
        condition_resolvers,
        groups=normalized_groups,
    )
    if errors:
        raise ValueError("Invalid RouteDeck LangGraph contract: " + "; ".join(errors))

    first_node = manifest.nodes[0].id if manifest.nodes else ""
    node_to_group = {
        node_id: group_id
        for group_id, node_ids in normalized_groups.items()
        for node_id in node_ids
    }

    def resolve_node(state: Mapping[str, Any]) -> str:
        candidate = (
            active_node_resolver(state)
            if active_node_resolver is not None
            else _default_active_node(state, first_node)
        )
        return candidate if candidate in handlers else first_node

    def resolve_group(state: Mapping[str, Any]) -> str:
        return node_to_group[resolve_node(state)]

    def turn_start(state: Mapping[str, Any]) -> dict[str, Any]:
        active_node = resolve_node(state)
        return {
            "active_stage_id": active_node,
            "route_group": node_to_group[active_node],
        }

    def default_route_action(_: Mapping[str, Any]) -> dict[str, Any]:
        return {}

    def default_finalize(_: Mapping[str, Any]) -> dict[str, Any]:
        return {}

    def group_boundary(_: Mapping[str, Any]) -> dict[str, Any]:
        return {}

    graph = StateGraph(state_schema)
    graph.add_node(entry_node_name, turn_start_node or turn_start)
    graph.add_node(route_action_node_name, route_action_node or default_route_action)
    graph.add_node(finalize_node_name, finalize_node or default_finalize)

    for group_id in normalized_groups:
        graph.add_node(group_id, group_boundary)

    for node_id, handler in handlers.items():
        graph.add_node(node_id, handler)

    graph.set_entry_point(entry_node_name)
    graph.add_edge(entry_node_name, route_action_node_name)
    graph.add_conditional_edges(
        route_action_node_name,
        resolve_group,
        {group_id: group_id for group_id in normalized_groups},
    )

    for group_id, node_ids in normalized_groups.items():
        graph.add_conditional_edges(
            group_id,
            resolve_node,
            {node_id: node_id for node_id in node_ids},
        )

    for node_id in handlers:
        graph.add_edge(node_id, finalize_node_name)
    graph.add_edge(finalize_node_name, END)

    return graph
