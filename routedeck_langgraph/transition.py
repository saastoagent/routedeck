from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from routedeck_core import RouteDeckEdgeSpec, RouteDeckManifest

from .types import ConditionResolvers


@dataclass(frozen=True)
class TransitionDiagnostics:
    from_stage: str
    to_stage: str
    condition: str | None
    edge_type: str | None
    action_id: str | None
    source: str = "route_deck"

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def matching_route_deck_edge(
    manifest: RouteDeckManifest,
    *,
    from_node: str,
    to_node: str,
    state: Mapping[str, Any],
    condition_resolvers: ConditionResolvers,
) -> RouteDeckEdgeSpec | None:
    for edge in manifest.edges:
        if edge.from_stage != from_node or edge.to_stage != to_node:
            continue
        if edge.condition is None:
            return edge
        resolver = condition_resolvers.get(edge.condition)
        if resolver is not None and resolver(edge, state):
            return edge
    return None


def assert_route_transition(
    manifest: RouteDeckManifest,
    *,
    from_node: str,
    to_node: str,
    state: Mapping[str, Any],
    condition_resolvers: ConditionResolvers,
) -> TransitionDiagnostics:
    if from_node == to_node:
        return TransitionDiagnostics(
            from_stage=from_node,
            to_stage=to_node,
            condition="same_node",
            edge_type=None,
            action_id=None,
        )

    edge = matching_route_deck_edge(
        manifest,
        from_node=from_node,
        to_node=to_node,
        state=state,
        condition_resolvers=condition_resolvers,
    )
    if edge is None:
        raise ValueError(f"RouteDeck transition {from_node!r} -> {to_node!r} is not executable.")

    return TransitionDiagnostics(
        from_stage=from_node,
        to_stage=to_node,
        condition=edge.condition,
        edge_type=edge.edge_type,
        action_id=edge.action_id,
    )
