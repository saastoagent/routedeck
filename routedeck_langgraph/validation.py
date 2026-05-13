from __future__ import annotations

from collections import Counter

from routedeck_core import RouteDeckManifest

from .types import ConditionResolvers, GroupMap, HandlerMap


def _normalized_groups(groups: GroupMap | None) -> dict[str, set[str]]:
    if groups is None:
        return {}
    return {group_id: set(nodes) for group_id, nodes in groups.items()}


def validate_langgraph_contract(
    manifest: RouteDeckManifest,
    handlers: HandlerMap,
    condition_resolvers: ConditionResolvers,
    groups: GroupMap | None = None,
) -> list[str]:
    errors: list[str] = []
    node_ids = {node.id for node in manifest.nodes}
    handler_ids = set(handlers.keys())

    missing_handlers = sorted(node_ids - handler_ids)
    for node_id in missing_handlers:
        errors.append(f"RouteDeck node has no LangGraph handler: {node_id}")

    extra_handlers = sorted(handler_ids - node_ids)
    for node_id in extra_handlers:
        errors.append(f"LangGraph handler has no RouteDeck node: {node_id}")

    missing_conditions = sorted(
        {
            edge.condition
            for edge in manifest.edges
            if edge.condition and edge.condition not in condition_resolvers
        }
    )
    for condition in missing_conditions:
        errors.append(f"RouteDeck edge condition has no LangGraph resolver: {condition}")

    normalized_groups = _normalized_groups(groups)
    if normalized_groups:
        grouped_nodes = [node_id for nodes in normalized_groups.values() for node_id in nodes]
        grouped_set = set(grouped_nodes)
        for node_id in sorted(grouped_set - node_ids):
            errors.append(f"LangGraph group references unknown RouteDeck node: {node_id}")
        for node_id in sorted(node_ids - grouped_set):
            errors.append(f"RouteDeck node is missing from LangGraph groups: {node_id}")
        duplicate_nodes = sorted(node_id for node_id, count in Counter(grouped_nodes).items() if count > 1)
        for node_id in duplicate_nodes:
            errors.append(f"RouteDeck node appears in multiple LangGraph groups: {node_id}")

    return errors
