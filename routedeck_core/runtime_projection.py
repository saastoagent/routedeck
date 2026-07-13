from __future__ import annotations

from typing import Any

from .models import (
    RouteDeckAvailableEntity,
    RouteDeckCapabilitySpec,
    RouteDeckContextLens,
    RouteDeckDispatchResult,
    RouteDeckEvent,
    RouteDeckLocation,
    RouteDeckManifest,
    RouteDeckNavGraph,
    RouteDeckNavGraphEdge,
    RouteDeckNavGraphNode,
    RouteDeckNavigationState,
    RouteDeckOperation,
    RouteDeckProjection,
    RouteDeckRuntimeEventType,
    RouteDeckRuntimeState,
    RouteDeckRuntimeStatus,
    RouteDeckSurface,
    RouteDeckSurfaceAffordance,
)


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
    node = next(
        (candidate for candidate in manifest.nodes if candidate.id == current_node),
        None,
    )
    return {
        "current_node": current_node,
        "reachable_nodes": reachable_nodes(manifest, current_node),
        "valid_actions": valid_actions or [],
        "blocked_actions": blocked_actions or [],
        "executed_nodes": executed_nodes or [],
        "progress": {
            "node_index": node_ids.index(current_node)
            if current_node in node_ids
            else None,
            "node_count": len(node_ids),
        },
        "recovery_prompts": [node.recovery_prompt]
        if node and node.recovery_prompt
        else [],
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
    capabilities: list[RouteDeckCapabilitySpec] | None = None,
    navgraph: RouteDeckNavGraph | dict[str, Any] | None = None,
    available_entities: list[RouteDeckAvailableEntity] | None = None,
    surface_affordances: list[RouteDeckSurfaceAffordance] | None = None,
    context_lens: RouteDeckContextLens | dict[str, Any] | None = None,
    projection_version: int = 1,
    diagnostics: dict[str, Any] | None = None,
) -> RouteDeckProjection:
    node = next(
        (candidate for candidate in manifest.nodes if candidate.id == current_node),
        None,
    )
    surface_map: dict[str, RouteDeckSurface] = {}
    for surface in surfaces or []:
        coerced = _coerce_surface_variant(surface, node)
        key = (
            coerced.name
            if coerced.name not in surface_map
            else (coerced.surface_id or coerced.name)
        )
        surface_map[key] = coerced
    navigation_state = _coerce_navigation(
        current_node=current_node, navigation=navigation
    )
    legal_operations = [
        operation
        for operation in operations or []
        if operation.execution_mode != "blocked"
    ]
    projection_context_lens = _coerce_context_lens(
        context_lens=context_lens,
        current_node=current_node,
        working_on=node.label if node else current_node,
        navigation=navigation_state,
        legal_operations=legal_operations,
    )
    return RouteDeckProjection(
        current_context=current_node,
        graph_node=current_node,
        projection_version=projection_version,
        legal_operations=legal_operations,
        surfaces=surface_map,
        presentation_state=presentation_state or {},
        navigation=navigation_state,
        context_lens=projection_context_lens,
        capabilities=capabilities
        if capabilities is not None
        else list(manifest.capabilities),
        navgraph=_coerce_navgraph(
            manifest=manifest,
            current_node=current_node,
            navigation=navigation_state,
            navgraph=navgraph,
        ),
        available_entities=available_entities or [],
        surface_affordances=surface_affordances or [],
        diagnostics=diagnostics or {},
    )


def build_dispatch_state_event(
    *,
    operation_id: str,
    state: RouteDeckRuntimeState,
    event_type: RouteDeckRuntimeEventType = "operation_completed",
    projection_version: int | None = None,
    payload: dict[str, Any] | None = None,
) -> RouteDeckEvent:
    event_payload = {
        "operation_id": operation_id,
        "state": state.model_dump(mode="json"),
        **(payload or {}),
    }
    return RouteDeckEvent(
        event_type=event_type,
        projection_version=projection_version
        if projection_version is not None
        else state.projection.projection_version,
        payload=event_payload,
    )


def build_runtime_state(
    *,
    projection: RouteDeckProjection,
    status: RouteDeckRuntimeStatus = "idle",
    graph_state: dict[str, Any] | None = None,
    location: str | None = None,
    diagnostics: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> RouteDeckRuntimeState:
    return RouteDeckRuntimeState(
        projection=projection,
        status=status,
        graph_state=dict(graph_state or {}),
        location=location,
        diagnostics=dict(
            projection.diagnostics if diagnostics is None else diagnostics
        ),
        metadata=dict(metadata or {}),
    )


def build_projection_update_event(
    *,
    state: RouteDeckRuntimeState,
    projection_version: int | None = None,
    payload: dict[str, Any] | None = None,
) -> RouteDeckEvent:
    return RouteDeckEvent(
        event_type="projection_update",
        projection_version=projection_version
        if projection_version is not None
        else state.projection.projection_version,
        payload={
            "projection": state.projection.model_dump(mode="json"),
            "state": state.model_dump(mode="json"),
            **(payload or {}),
        },
    )


def build_operation_completed_event(
    *,
    operation_id: str,
    projection: RouteDeckProjection,
    projection_version: int | None = None,
    payload: dict[str, Any] | None = None,
) -> RouteDeckEvent:
    return RouteDeckEvent(
        event_type="operation_completed",
        projection_version=projection_version
        if projection_version is not None
        else projection.projection_version,
        payload={
            "operation_id": operation_id,
            "projection": projection.model_dump(mode="json"),
            **(payload or {}),
        },
    )


def build_dispatch_result_completed_event(
    *,
    operation_id: str,
    state: RouteDeckRuntimeState,
    active_surface: RouteDeckSurface | None = None,
    messages: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> RouteDeckEvent:
    metadata = dict(metadata or {})
    return build_operation_completed_event(
        operation_id=operation_id,
        projection=state.projection,
        payload={
            "state": dict(state.graph_state or {}),
            "active_surface": active_surface.model_dump(mode="json")
            if active_surface
            else None,
            "messages": list(messages or []),
            "replace_path": state.location or metadata.get("replace_path"),
        },
    )


def build_dispatch_result(
    *,
    operation_id: str,
    state: RouteDeckRuntimeState,
    accepted: bool = True,
    active_surface: RouteDeckSurface | None = None,
    messages: list[dict[str, Any]] | None = None,
    events: list[RouteDeckEvent] | None = None,
    metadata: dict[str, Any] | None = None,
) -> RouteDeckDispatchResult:
    return RouteDeckDispatchResult(
        operation_id=operation_id,
        accepted=accepted,
        state=state,
        active_surface=active_surface,
        messages=list(messages or []),
        events=list(events)
        if events is not None
        else [
            build_dispatch_result_completed_event(
                operation_id=operation_id,
                state=state,
                active_surface=active_surface,
                messages=messages,
                metadata=metadata,
            )
        ],
        metadata=dict(metadata or {}),
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
        state = RouteDeckNavigationState(
            current=RouteDeckLocation(node_id=current_node)
        )
    return state.model_copy(
        update={
            "can_back": bool(state.back_stack),
            "can_forward": bool(state.forward_stack),
            "can_cancel": bool(
                state.back_stack or state.current.node_id != current_node
            ),
        }
    )


def _coerce_context_lens(
    *,
    context_lens: RouteDeckContextLens | dict[str, Any] | None,
    current_node: str,
    working_on: str,
    navigation: RouteDeckNavigationState,
    legal_operations: list[RouteDeckOperation],
) -> RouteDeckContextLens:
    if context_lens is None:
        lens = RouteDeckContextLens(current_node=current_node, working_on=working_on)
    elif isinstance(context_lens, RouteDeckContextLens):
        lens = context_lens
    else:
        lens = RouteDeckContextLens.model_validate(context_lens)
    return lens.model_copy(
        update={
            "current_node": current_node,
            "active_surface_id": navigation.current.surface_id,
            "route_params": dict(navigation.current.params),
            "legal_operation_ids": [operation.id for operation in legal_operations],
        }
    )


def _coerce_navgraph(
    *,
    manifest: RouteDeckManifest,
    current_node: str,
    navigation: RouteDeckNavigationState,
    navgraph: RouteDeckNavGraph | dict[str, Any] | None,
) -> RouteDeckNavGraph:
    if isinstance(navgraph, RouteDeckNavGraph):
        return navgraph
    if isinstance(navgraph, dict):
        payload = dict(navgraph)
        payload.setdefault("current", navigation.current.model_dump(mode="json"))
        return RouteDeckNavGraph.model_validate(payload)

    return RouteDeckNavGraph(
        current=navigation.current,
        nodes=[
            RouteDeckNavGraphNode(
                id=node.id,
                label=node.label,
                capability_ids=[node.capability_id] if node.capability_id else [],
            )
            for node in manifest.nodes
            if node.show_in_navgraph
        ],
        edges=[
            RouteDeckNavGraphEdge(
                source=edge.from_stage,
                target=edge.to_stage,
                action_id=edge.action_id,
                capability_id=edge.capability_id,
            )
            for edge in manifest.edges
        ],
        reachable=reachable_nodes(manifest, current_node),
    )
