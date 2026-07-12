"""Reusable state projection helpers for RouteDeck runtimes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from .models import (
    RouteDeckContextLens,
    RouteDeckGraphState,
    RouteDeckManifest,
    RouteDeckOperation,
    RouteDeckProjection,
    RouteDeckSurface,
)
from .operations import RouteDeckOperationPolicy
from .runtime import build_projection
from .surfaces import RouteDeckSurfaceRegistry


class RouteDeckStateProjector:
    """Builds RouteDeck projection primitives from product runtime inputs."""

    OperationPolicy: ClassVar[type[RouteDeckOperationPolicy]] = RouteDeckOperationPolicy
    SurfaceRegistry: ClassVar[type[RouteDeckSurfaceRegistry]] = RouteDeckSurfaceRegistry
    manifest: ClassVar[RouteDeckManifest | None] = None
    operation_review_component: ClassVar[str] = "RouteDeckOperationReviewSurface"

    def __init__(
        self,
        *,
        manifest: RouteDeckManifest | None = None,
        operation_policy: RouteDeckOperationPolicy | None = None,
        surface_registry: RouteDeckSurfaceRegistry | None = None,
        operation_review_component: str | None = None,
    ) -> None:
        resolved_manifest = manifest or type(self).manifest
        if resolved_manifest is None:
            raise TypeError(
                "RouteDeckStateProjector requires a manifest or subclass manifest"
            )
        self._manifest = resolved_manifest
        self.operation_policy = operation_policy or self.OperationPolicy()
        self.surface_registry = surface_registry or self.SurfaceRegistry()
        self._operation_review_component = (
            operation_review_component
            if operation_review_component is not None
            else type(self).operation_review_component
        )

    def operations_for_actions(
        self, actions: Sequence[Any]
    ) -> list[RouteDeckOperation]:
        return [
            self.operation_policy.operation_for_action(action) for action in actions
        ]

    def resolve_current_surface_id(
        self,
        *,
        active_surface_id: str | None,
        pending_operation_id: str | None,
        default_surface_id: str | None,
    ) -> str | None:
        review_operation_id = self.surface_registry.operation_id_from_surface_id(
            active_surface_id
        )
        if review_operation_id and pending_operation_id != review_operation_id:
            active_surface_id = None
        return active_surface_id or default_surface_id

    def default_surface_id_for_state(self, state: RouteDeckGraphState) -> str | None:
        return self.surface_registry.default_surface_id_for(
            state.node,
            pending_operation_id=state.pending_operation_id,
        )

    def resolve_current_surface_id_for_state(
        self, state: RouteDeckGraphState
    ) -> str | None:
        return self.resolve_current_surface_id(
            active_surface_id=state.active_surface_id,
            pending_operation_id=state.pending_operation_id,
            default_surface_id=self.default_surface_id_for_state(state),
        )

    def default_surface_by_node_for_state(
        self, state: RouteDeckGraphState
    ) -> dict[str, str]:
        defaults: dict[str, str] = {}
        for node in self._manifest.nodes:
            node_state = state.model_copy(
                update={
                    "node": node.id,
                    "active_surface_id": None,
                    "pending_operation_id": None,
                    "pending_operation_args": {},
                    "route_params": {},
                }
            )
            default_surface_id = self.default_surface_id_for_state(node_state)
            if default_surface_id:
                defaults[node.id] = default_surface_id
        return defaults

    def navigation_for_state(self, state: RouteDeckGraphState) -> dict[str, Any]:
        return {
            "current": {
                "node_id": state.node,
                "surface_id": self.resolve_current_surface_id_for_state(state),
                "params": dict(state.route_params),
            },
            "back_stack": [
                location.model_dump(mode="json")
                for location in state.navigation_back_stack
            ],
            "forward_stack": [
                location.model_dump(mode="json")
                for location in state.navigation_forward_stack
            ],
        }

    def review_surface_props(
        self, state: RouteDeckGraphState, **context: Any
    ) -> dict[str, Any]:
        return {}

    def surfaces_with_review(
        self,
        state: RouteDeckGraphState,
        surfaces: Sequence[RouteDeckSurface],
        *,
        props: Mapping[str, Any] | None = None,
        component: str | None = None,
        **context: Any,
    ) -> list[RouteDeckSurface]:
        projected_surfaces = list(surfaces)
        if not state.pending_operation_id:
            return projected_surfaces
        review_props = (
            props if props is not None else context.get("review_surface_props")
        )
        if review_props is None:
            review_props = self.review_surface_props(state, **context)
        review_surface = self.surface_registry.operation_review_surface(
            node_id=state.node,
            operation_id=state.pending_operation_id,
            operation_args=state.pending_operation_args,
            component=component or self._operation_review_component,
            props=review_props,
        )
        for index, surface in enumerate(projected_surfaces):
            if surface.role == "active":
                return [
                    *projected_surfaces[:index],
                    review_surface,
                    *projected_surfaces[index:],
                ]
        return [*projected_surfaces, review_surface]

    def active_surfaces_with_review(
        self,
        state: RouteDeckGraphState,
        surfaces: Sequence[RouteDeckSurface],
        *,
        props: Mapping[str, Any] | None = None,
        component: str | None = None,
        **context: Any,
    ) -> list[RouteDeckSurface]:
        return self.surfaces_with_review(
            state,
            surfaces,
            props=props,
            component=component,
            **context,
        )

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
                "show_in_capability_rail": getattr(
                    node, "show_in_capability_rail", True
                ),
                "default_surface_id": defaults.get(node.id),
            }
            for node in self._manifest.nodes
        }

    def current_context_for_state(
        self, state: RouteDeckGraphState, **context: Any
    ) -> str | None:
        current_context = context.get("current_context")
        return str(current_context) if current_context is not None else state.node

    def actions_for_state(
        self, state: RouteDeckGraphState, **context: Any
    ) -> Sequence[Any]:
        actions = context.get("actions")
        return list(actions) if isinstance(actions, Sequence) else []

    def surfaces_for_state(
        self, state: RouteDeckGraphState, **context: Any
    ) -> Sequence[RouteDeckSurface]:
        surfaces = context.get("surfaces")
        return list(surfaces) if isinstance(surfaces, Sequence) else []

    def presentation_state_for_state(
        self, state: RouteDeckGraphState, **context: Any
    ) -> Mapping[str, Any]:
        presentation_state = context.get("presentation_state")
        return (
            dict(presentation_state) if isinstance(presentation_state, Mapping) else {}
        )

    def diagnostics_for_state(
        self, state: RouteDeckGraphState, **context: Any
    ) -> Mapping[str, Any]:
        diagnostics = context.get("diagnostics")
        return dict(diagnostics) if isinstance(diagnostics, Mapping) else {}

    def context_lens_for_state(
        self, state: RouteDeckGraphState, **context: Any
    ) -> RouteDeckContextLens | dict[str, Any] | None:
        context_lens = context.get("context_lens")
        if context_lens is None:
            return None
        if isinstance(context_lens, RouteDeckContextLens):
            return context_lens
        if isinstance(context_lens, Mapping):
            return dict(context_lens)
        raise TypeError("context_lens must be a RouteDeckContextLens or mapping")

    def project_state(
        self,
        state: RouteDeckGraphState,
        *,
        projection_version: int = 1,
        **context: Any,
    ) -> RouteDeckProjection:
        surface_context = {
            key: value
            for key, value in context.items()
            if key not in {"surfaces", "props", "component", "review_surface_props"}
        }
        return RouteDeckStateProjector.project(
            self,
            current_node=state.node,
            current_context=self.current_context_for_state(state, **context),
            actions=self.actions_for_state(state, **context),
            surfaces=self.surfaces_with_review(
                state,
                self.surfaces_for_state(state, **context),
                props=context.get("review_surface_props"),
                **surface_context,
            ),
            navigation=self.navigation_for_state(state),
            context_lens=self.context_lens_for_state(state, **context),
            presentation_state=self.presentation_state_for_state(state, **context),
            projection_version=projection_version,
            diagnostics=self.diagnostics_for_state(state, **context),
        )

    def project(
        self,
        *,
        current_node: str,
        actions: Sequence[Any],
        surfaces: Sequence[RouteDeckSurface],
        navigation: Mapping[str, Any],
        context_lens: RouteDeckContextLens | Mapping[str, Any] | None = None,
        presentation_state: Mapping[str, Any] | None = None,
        projection_version: int = 1,
        diagnostics: Mapping[str, Any] | None = None,
        current_context: str | None = None,
    ) -> RouteDeckProjection:
        resolved_context_lens = (
            context_lens
            if context_lens is None or isinstance(context_lens, RouteDeckContextLens)
            else dict(context_lens)
        )
        projection = build_projection(
            self._manifest,
            current_node=current_node,
            operations=self.operations_for_actions(actions),
            surfaces=list(surfaces),
            navigation=dict(navigation),
            context_lens=resolved_context_lens,
            presentation_state=dict(presentation_state or {}),
            projection_version=projection_version,
            diagnostics=dict(diagnostics or {}),
        )
        if current_context is None:
            return projection
        return projection.model_copy(update={"current_context": current_context})
