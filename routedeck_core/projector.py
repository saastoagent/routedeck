"""Reusable state projection helpers for RouteDeck runtimes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .models import RouteDeckManifest, RouteDeckOperation, RouteDeckProjection, RouteDeckSurface
from .operations import RouteDeckOperationPolicy
from .runtime import build_projection
from .surfaces import RouteDeckSurfaceRegistry


class RouteDeckStateProjector:
    """Builds RouteDeck projection primitives from product runtime inputs."""

    def __init__(
        self,
        *,
        manifest: RouteDeckManifest,
        operation_policy: RouteDeckOperationPolicy | None = None,
        surface_registry: RouteDeckSurfaceRegistry | None = None,
    ) -> None:
        self.manifest = manifest
        self.operation_policy = operation_policy or RouteDeckOperationPolicy()
        self.surface_registry = surface_registry or RouteDeckSurfaceRegistry()

    def operations_for_actions(self, actions: Sequence[Any]) -> list[RouteDeckOperation]:
        return [self.operation_policy.operation_for_action(action) for action in actions]

    def resolve_current_surface_id(
        self,
        *,
        active_surface_id: str | None,
        pending_operation_id: str | None,
        default_surface_id: str | None,
    ) -> str | None:
        review_operation_id = self.surface_registry.operation_id_from_surface_id(active_surface_id)
        if review_operation_id and pending_operation_id != review_operation_id:
            active_surface_id = None
        return active_surface_id or default_surface_id

    def node_hierarchy(
        self,
        *,
        default_surface_by_node: Mapping[str, str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        defaults = dict(default_surface_by_node or {})
        return {
            node.id: {
                "parent": node.parent,
                "node_kind": getattr(node, "node_kind", "workflow"),
                "capability_id": getattr(node, "capability_id", None),
                "cancel_target_node": getattr(node, "cancel_target_node", None),
                "dirty_policy": getattr(node, "dirty_policy", "none"),
                "show_in_capability_rail": getattr(node, "show_in_capability_rail", True),
                "default_surface_id": defaults.get(node.id),
            }
            for node in self.manifest.nodes
        }

    def project(
        self,
        *,
        current_node: str,
        actions: Sequence[Any],
        surfaces: Sequence[RouteDeckSurface],
        navigation: Mapping[str, Any],
        presentation_state: Mapping[str, Any] | None = None,
        projection_version: int = 1,
        diagnostics: Mapping[str, Any] | None = None,
        current_context: str | None = None,
    ) -> RouteDeckProjection:
        projection = build_projection(
            self.manifest,
            current_node=current_node,
            operations=self.operations_for_actions(actions),
            surfaces=list(surfaces),
            navigation=dict(navigation),
            presentation_state=dict(presentation_state or {}),
            projection_version=projection_version,
            diagnostics=dict(diagnostics or {}),
        )
        if current_context is None:
            return projection
        return projection.model_copy(update={"current_context": current_context})
