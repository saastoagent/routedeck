"""Authoring helpers for building RouteDeck manifests."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal, Self

from .models import (
    RouteDeckActionCategory,
    RouteDeckActionEmphasis,
    RouteDeckActionKind,
    RouteDeckActionPlacement,
    RouteDeckActionSpec,
    RouteDeckCapabilitySpec,
    RouteDeckDirtyPolicy,
    RouteDeckEdgeSpec,
    RouteDeckFieldSpec,
    RouteDeckInvocationKind,
    RouteDeckManifest,
    RouteDeckNodeKind,
    RouteDeckNodeSpec,
    RouteDeckSensitivePolicy,
)


def _copy_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _copy_surface_map(
    value: Mapping[str, Sequence[str]] | None,
) -> dict[str, list[str]]:
    return {
        surface_id: list(variants) for surface_id, variants in (value or {}).items()
    }


def route_deck_field(**kwargs: Any) -> RouteDeckFieldSpec:
    """Create a field spec from keyword arguments."""

    return RouteDeckFieldSpec(**kwargs)


def route_deck_node(
    node_id: str,
    label: str,
    *,
    lane: str,
    description: str,
    actions: Sequence[str] | None = None,
    expected_input: str | None = None,
    recovery: str | None = None,
    recovery_prompt: str | None = None,
    prompt_placeholder: str | None = None,
    allowed_surfaces: Mapping[str, Sequence[str]] | None = None,
    default_surfaces: Mapping[str, str] | None = None,
    parent: str | None = None,
    node_kind: RouteDeckNodeKind = "workflow",
    capability_id: str | None = None,
    show_in_navgraph: bool = True,
    show_in_capability_rail: bool = True,
    cancel_target_node: str | None = None,
    dirty_policy: RouteDeckDirtyPolicy = "none",
) -> RouteDeckNodeSpec:
    """Create a node spec while keeping caller-owned containers isolated."""

    return RouteDeckNodeSpec(
        id=node_id,
        label=label,
        lane=lane,
        description=description,
        allowed_actions=list(actions or []),
        expected_input=expected_input,
        recovery_prompt=recovery_prompt if recovery_prompt is not None else recovery,
        prompt_placeholder=prompt_placeholder,
        allowed_surfaces=_copy_surface_map(allowed_surfaces),
        default_surfaces=dict(default_surfaces or {}),
        parent=parent,
        node_kind=node_kind,
        capability_id=capability_id,
        show_in_navgraph=show_in_navgraph,
        show_in_capability_rail=show_in_capability_rail,
        cancel_target_node=cancel_target_node,
        dirty_policy=dirty_policy,
    )


def route_deck_action(
    action_id: str,
    label: str,
    *,
    description: str | None = None,
    kind: RouteDeckActionKind = "button",
    category: RouteDeckActionCategory | None = None,
    emphasis: RouteDeckActionEmphasis = "secondary",
    fields: Sequence[RouteDeckFieldSpec] | None = None,
    invocation_kind: RouteDeckInvocationKind | None = None,
    allowed_nodes: Sequence[str] | None = None,
    placement: RouteDeckActionPlacement | None = None,
    capability_id: str | None = None,
    payload: Mapping[str, Any] | None = None,
    visibility: Literal["contextual", "persistent", "dynamic"] = "contextual",
    recovery_prompt: str | None = None,
    sensitive: bool = False,
) -> RouteDeckActionSpec:
    """Create an action spec from product configuration."""

    return RouteDeckActionSpec(
        id=action_id,
        label=label,
        description=description,
        kind=kind,
        category=category,
        emphasis=emphasis,
        fields=list(fields or []),
        invocation_kind=invocation_kind,
        allowed_nodes=list(allowed_nodes or []),
        placement=placement,
        capability_id=capability_id,
        payload=_copy_mapping(payload),
        visibility=visibility,
        recovery_prompt=recovery_prompt,
        sensitive=sensitive,
    )


def route_deck_edge(
    from_node: str,
    to_node: str,
    *,
    action_id: str | None = None,
    edge_type: str | None = None,
    condition: str | None = None,
    explanation: str | None = None,
    capability_id: str | None = None,
) -> RouteDeckEdgeSpec:
    """Create an edge spec with RouteDeck's action/runtime defaulting."""

    return RouteDeckEdgeSpec.model_validate(
        {
            "from": from_node,
            "to": to_node,
            "type": edge_type or ("action" if action_id else "runtime"),
            "action_id": action_id,
            "condition": condition,
            "explanation": explanation,
            "capability_id": capability_id,
        }
    )


class RouteDeckManifestBuilder:
    """Small fluent builder for assembling a RouteDeck manifest."""

    def __init__(self, version: str) -> None:
        self.version = version
        self._nodes: list[RouteDeckNodeSpec] = []
        self._edges: list[RouteDeckEdgeSpec] = []
        self._actions: list[RouteDeckActionSpec] = []
        self._capabilities: list[RouteDeckCapabilitySpec] = []
        self._policies: dict[str, Any] = {}
        self._test_paths: list[dict[str, Any]] = []

    def add_node(self, node: RouteDeckNodeSpec) -> Self:
        self._nodes.append(node)
        return self

    def add_nodes(self, nodes: Iterable[RouteDeckNodeSpec]) -> Self:
        self._nodes.extend(nodes)
        return self

    def node(self, node_id: str, label: str, **kwargs: Any) -> Self:
        return self.add_node(route_deck_node(node_id, label, **kwargs))

    def add_edge(self, edge: RouteDeckEdgeSpec) -> Self:
        self._edges.append(edge)
        return self

    def add_edges(self, edges: Iterable[RouteDeckEdgeSpec]) -> Self:
        self._edges.extend(edges)
        return self

    def edge(self, from_node: str, to_node: str, **kwargs: Any) -> Self:
        return self.add_edge(route_deck_edge(from_node, to_node, **kwargs))

    def add_action(self, action: RouteDeckActionSpec) -> Self:
        self._actions.append(action)
        return self

    def add_actions(self, actions: Iterable[RouteDeckActionSpec]) -> Self:
        self._actions.extend(actions)
        return self

    def action(self, action_id: str, label: str, **kwargs: Any) -> Self:
        return self.add_action(route_deck_action(action_id, label, **kwargs))

    def add_capability(self, capability: RouteDeckCapabilitySpec) -> Self:
        self._capabilities.append(capability)
        return self

    def add_capabilities(self, capabilities: Iterable[RouteDeckCapabilitySpec]) -> Self:
        self._capabilities.extend(capabilities)
        return self

    def policy(self, key: str, value: Any) -> Self:
        self._policies[key] = value
        return self

    def sensitive_policy(self, **kwargs: Any) -> Self:
        return self.policy("sensitive", RouteDeckSensitivePolicy(**kwargs).model_dump())

    def test_path(self, path_id: str, nodes: Sequence[str], **metadata: Any) -> Self:
        self._test_paths.append({"id": path_id, "nodes": list(nodes), **metadata})
        return self

    def build(self) -> RouteDeckManifest:
        return RouteDeckManifest(
            version=self.version,
            nodes=list(self._nodes),
            edges=list(self._edges),
            actions=list(self._actions),
            capabilities=list(self._capabilities),
            policies=dict(self._policies),
            test_paths=[dict(path) for path in self._test_paths],
        )
