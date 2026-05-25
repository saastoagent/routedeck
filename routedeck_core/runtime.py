from __future__ import annotations

from typing import Any, AsyncIterator, Protocol, runtime_checkable

from .models import (
    RouteDeckDispatchInput,
    RouteDeckDispatchResult,
    RouteDeckEvent,
    RouteDeckLocation,
    RouteDeckIntrospection,
    RouteDeckManifest,
    RouteDeckNavigationState,
    RouteDeckOperation,
    RouteDeckProjection,
    RouteDeckRuntimeState,
    RouteDeckSurface,
)


@runtime_checkable
class RouteDeckRuntime(Protocol):
    async def snapshot(self, context: dict[str, Any] | None = None) -> RouteDeckRuntimeState:
        ...

    async def projection(self, context: dict[str, Any] | None = None) -> RouteDeckProjection:
        ...

    async def dispatch(
        self,
        request: RouteDeckDispatchInput,
        context: dict[str, Any] | None = None,
    ) -> RouteDeckDispatchResult:
        ...

    async def inspect(
        self,
        query: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> RouteDeckIntrospection:
        ...

    def stream(self, context: dict[str, Any] | None = None) -> AsyncIterator[RouteDeckEvent]:
        ...


def reachable_nodes(manifest: RouteDeckManifest, node_id: str | None) -> list[str]:
    if not node_id:
        return []
    return [edge.to_stage for edge in manifest.edges if edge.from_stage == node_id]


def build_runtime_snapshot(
    manifest: RouteDeckManifest,
    *,
    current_node: str | None,
    valid_actions: list[dict[str, Any]] | None = None,
    blocked_actions: list[dict[str, str]] | None = None,
    executed_nodes: list[str] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node_ids = [node.id for node in manifest.nodes]
    node = next((candidate for candidate in manifest.nodes if candidate.id == current_node), None)
    return {
        "current_node": current_node,
        "reachable_nodes": reachable_nodes(manifest, current_node),
        "valid_actions": valid_actions or [],
        "blocked_actions": blocked_actions or [],
        "executed_nodes": executed_nodes or [],
        "progress": {
            "node_index": node_ids.index(current_node) if current_node in node_ids else None,
            "node_count": len(node_ids),
        },
        "recovery_prompts": [node.recovery_prompt] if node and node.recovery_prompt else [],
        "diagnostics": diagnostics or {},
    }


def build_projection(
    manifest: RouteDeckManifest,
    *,
    current_node: str,
    operations: list[RouteDeckOperation] | None = None,
    surfaces: list[RouteDeckSurface] | None = None,
    presentation_state: dict[str, Any] | None = None,
    navigation: dict[str, Any] | RouteDeckNavigationState | None = None,
    projection_version: int = 1,
    diagnostics: dict[str, Any] | None = None,
) -> RouteDeckProjection:
    node = next((candidate for candidate in manifest.nodes if candidate.id == current_node), None)
    surface_map: dict[str, RouteDeckSurface] = {}
    for surface in surfaces or []:
        coerced = _coerce_surface_variant(surface, node)
        key = coerced.name if coerced.name not in surface_map else (coerced.surface_id or coerced.name)
        surface_map[key] = coerced
    return RouteDeckProjection(
        current_context=current_node,
        graph_node=current_node,
        projection_version=projection_version,
        legal_operations=[operation for operation in operations or [] if operation.execution_mode != "blocked"],
        surfaces=surface_map,
        presentation_state=presentation_state or {},
        navigation=_coerce_navigation(current_node=current_node, navigation=navigation),
        diagnostics=diagnostics or {},
    )


def _coerce_surface_variant(surface: RouteDeckSurface, node: Any) -> RouteDeckSurface:
    if node is None:
        return surface
    allowed = node.allowed_surfaces.get(surface.name)
    if not allowed or surface.variant in allowed:
        return surface
    default_variant = node.default_surfaces.get(surface.name) or allowed[0]
    return surface.model_copy(update={"variant": default_variant})


def _coerce_navigation(
    *,
    current_node: str,
    navigation: dict[str, Any] | RouteDeckNavigationState | None,
) -> RouteDeckNavigationState:
    if isinstance(navigation, RouteDeckNavigationState):
        state = navigation
    elif isinstance(navigation, dict):
        payload = dict(navigation)
        payload.setdefault("current", {"node_id": current_node})
        state = RouteDeckNavigationState.model_validate(payload)
    else:
        state = RouteDeckNavigationState(current=RouteDeckLocation(node_id=current_node))
    return state.model_copy(
        update={
            "can_back": bool(state.back_stack),
            "can_forward": bool(state.forward_stack),
            "can_cancel": bool(state.back_stack or state.current.node_id != current_node),
        }
    )
