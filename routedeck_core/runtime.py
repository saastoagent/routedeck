from __future__ import annotations

from typing import Any, AsyncIterator, ClassVar, Generic, Protocol, TypeVar, runtime_checkable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .authoring import RouteDeckManifestBuilder
from .dispatch import RouteDeckActionResult
from .models import (
    RouteDeckAvailableEntity,
    RouteDeckCapabilitySpec,
    RouteDeckContextLens,
    RouteDeckDispatchInput,
    RouteDeckDispatchResult,
    RouteDeckEvent,
    RouteDeckEventType,
    RouteDeckGraphMessage,
    RouteDeckGraphState,
    RouteDeckLocation,
    RouteDeckIntrospection,
    RouteDeckManifest,
    RouteDeckNavGraph,
    RouteDeckNavGraphEdge,
    RouteDeckNavGraphNode,
    RouteDeckNavigationState,
    RouteDeckOperation,
    RouteDeckProjection,
    RouteDeckRuntimeState,
    RouteDeckSurface,
    RouteDeckSurfaceAffordance,
)
from .navigation import RouteDeckGraphNavigationController
from .operations import RouteDeckOperationPolicy, RouteDeckOperationRequestPolicy, RouteDeckRouteActionIds
from .surfaces import RouteDeckSurfaceRegistry


StateT = TypeVar("StateT", bound=RouteDeckGraphState)
MessageT = TypeVar("MessageT", bound=RouteDeckGraphMessage)


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


class RouteDeckRuntimeBase(Generic[StateT, MessageT]):
    """Subclass-owned runtime for products that extend RouteDeck.

    Product runtimes subclass this type and override business hooks such as
    ``active_surfaces`` and ``execute_action``. RouteDeck keeps ownership of the
    runtime envelope: projection assembly, route dispatch, review staging,
    pending-operation state, active-surface resolution, and runtime events.
    """

    State: ClassVar[type[StateT]] = RouteDeckGraphState
    Surface: ClassVar[type[RouteDeckSurface]] = RouteDeckSurface
    SurfaceRegistry: ClassVar[type[RouteDeckSurfaceRegistry]] = RouteDeckSurfaceRegistry
    NavigationController: ClassVar[type[RouteDeckGraphNavigationController]] = RouteDeckGraphNavigationController
    OperationPolicy: ClassVar[type[RouteDeckOperationPolicy]] = RouteDeckOperationPolicy
    OperationRequestPolicy: ClassVar[type[RouteDeckOperationRequestPolicy]] = RouteDeckOperationRequestPolicy
    manifest: ClassVar[RouteDeckManifest]
    initial_node: ClassVar[str] = "home"
    route_action_ids: ClassVar[RouteDeckRouteActionIds] = RouteDeckRouteActionIds(
        open_node="route.open_node",
        switch_surface="route.switch_surface",
        back="route.back",
        forward="route.forward",
        cancel="route.cancel",
    )
    operation_review_component: ClassVar[str] = "RouteDeckOperationReviewSurface"

    def __init__(self) -> None:
        self._action_by_id = {action.id: action for action in self.manifest.actions}
        self._node_by_id = {node.id: node for node in self.manifest.nodes}
        self._surface_registry = self.build_surface_registry()
        self._navigation = self.build_navigation_controller()
        self._operation_policy = self.build_operation_policy()
        self._operation_requests = self.build_operation_request_policy()
        self._presentation_state_by_key: dict[str, dict[str, Any]] = {}

    @classmethod
    def manifest_builder(cls, version: str) -> RouteDeckManifestBuilder:
        return RouteDeckManifestBuilder(version)

    def build_surface_registry(self) -> RouteDeckSurfaceRegistry:
        if self.SurfaceRegistry is RouteDeckSurfaceRegistry:
            return self.SurfaceRegistry(
                active_components_by_node={
                    node.id: node.id
                    for node in self.manifest.nodes
                    if node.allowed_surfaces or node.default_surfaces
                }
            )
        return self.SurfaceRegistry()

    def build_navigation_controller(self) -> RouteDeckGraphNavigationController:
        return self.NavigationController(
            surface_registry=self._surface_registry,
            node_by_id=self._node_by_id,
        )

    def build_operation_policy(self) -> RouteDeckOperationPolicy:
        if self.OperationPolicy is RouteDeckOperationPolicy:
            return self.OperationPolicy(
                target_nodes_by_action=self._target_nodes_by_action(),
            )
        return self.OperationPolicy()

    def build_operation_request_policy(self) -> RouteDeckOperationRequestPolicy:
        return self.OperationRequestPolicy(
            navigation=self._navigation,
            surface_registry=self._surface_registry,
            route_actions=self.route_action_ids,
        )

    def build_state_projector(self, **kwargs: Any) -> Any:
        from .projector import RouteDeckStateProjector

        return RouteDeckStateProjector(
            manifest=self.manifest,
            operation_policy=self._operation_policy,
            surface_registry=self._surface_registry,
            operation_review_component=self.operation_review_component,
            **kwargs,
        )

    async def snapshot(self, context: dict[str, Any] | None = None) -> RouteDeckRuntimeState:
        ctx = context or {}
        state = await self.prepare_state(ctx)
        return await self.runtime_state_from_state(
            state=state,
            context=ctx,
            projection_version=self.projection_version_from_context(ctx),
        )

    async def projection(self, context: dict[str, Any] | None = None) -> RouteDeckProjection:
        return (await self.snapshot(context)).projection

    async def dispatch(
        self,
        request: RouteDeckDispatchInput,
        context: dict[str, Any] | None = None,
    ) -> RouteDeckDispatchResult:
        ctx = context or {}
        state = await self.prepare_dispatch_state(request, ctx)
        projection = await self.project_state(
            state,
            context=ctx,
            projection_version=request.projection_version or self.projection_version_from_context(ctx),
        )
        operation = next((candidate for candidate in projection.legal_operations if candidate.id == request.operation_id), None)
        if operation is None:
            raise ValueError("Operation is not legal from the current RouteDeck state")

        payload = self._operation_requests.validated_payload(
            state=state,
            operation=operation,
            args=request.args,
            projection=projection,
        )
        payload = {**operation.payload, **payload}

        if operation.id == self.route_action_ids.open_node:
            self._navigation.open_node(state, payload)
            runtime_state = await self.runtime_state_from_state(state=state, context=ctx, projection_version=self._next_projection_version(request))
            return self._dispatch_result(
                operation_id=operation.id,
                state=runtime_state,
                metadata=self.dispatch_metadata_for_state(state, ctx),
            )
        if operation.id == self.route_action_ids.switch_surface:
            self._navigation.switch_surface(state, payload)
            runtime_state = await self.runtime_state_from_state(state=state, context=ctx, projection_version=self._next_projection_version(request))
            return self._dispatch_result(
                operation_id=operation.id,
                state=runtime_state,
                metadata=self.dispatch_metadata_for_state(state, ctx),
            )
        if operation.id == self.route_action_ids.back:
            self._navigation.move_back(state)
            runtime_state = await self.runtime_state_from_state(state=state, context=ctx, projection_version=self._next_projection_version(request))
            return self._dispatch_result(
                operation_id=operation.id,
                state=runtime_state,
                metadata=self.dispatch_metadata_for_state(state, ctx),
            )
        if operation.id == self.route_action_ids.forward:
            self._navigation.move_forward(state)
            runtime_state = await self.runtime_state_from_state(state=state, context=ctx, projection_version=self._next_projection_version(request))
            return self._dispatch_result(
                operation_id=operation.id,
                state=runtime_state,
                metadata=self.dispatch_metadata_for_state(state, ctx),
            )
        if operation.id == self.route_action_ids.cancel:
            self._navigation.cancel(state)
            runtime_state = await self.runtime_state_from_state(state=state, context=ctx, projection_version=self._next_projection_version(request))
            return self._dispatch_result(
                operation_id=operation.id,
                state=runtime_state,
                metadata=self.dispatch_metadata_for_state(state, ctx),
            )

        if self.should_stage_operation_review(state=state, operation=operation, context=ctx):
            review_state = self._operation_requests.review_state_for_operation(
                state=state,
                operation=operation,
                args=payload,
            )
            runtime_state = await self.runtime_state_from_state(state=review_state, context=ctx, projection_version=self._next_projection_version(request))
            return self._dispatch_result(
                operation_id=operation.id,
                state=runtime_state,
                metadata=self.dispatch_metadata_for_state(review_state, ctx),
            )

        previous_location = self._navigation.current_location(state)
        result = await self.execute_action_with_context(operation.id, state, payload, ctx)
        result.state.pending_operation_id = None
        result.state.pending_operation_args = {}
        if result.state.node != previous_location.node_id and result.state.active_surface_id == previous_location.surface_id:
            result.state.active_surface_id = None
        self._navigation.push_navigation(result.state, previous_location)
        runtime_state = await self.runtime_state_from_state(state=result.state, context=ctx, projection_version=self._next_projection_version(request))
        return self._dispatch_result(
            operation_id=operation.id,
            state=runtime_state,
            messages=[message.model_dump(mode="json") for message in result.messages],
            metadata=self.dispatch_metadata_for_state(result.state, ctx),
        )

    async def inspect(
        self,
        query: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> RouteDeckIntrospection:
        ctx = {**(context or {}), **(query or {})}
        state = await self.prepare_state(ctx)
        projection = await self.project_state(
            state,
            context=ctx,
            projection_version=self.projection_version_from_context(ctx),
        )
        return RouteDeckIntrospection(
            current_node=projection.graph_node,
            reachable_nodes=reachable_nodes(self.manifest, projection.graph_node),
            legal_operations=[operation.model_dump(mode="json") for operation in projection.legal_operations],
            surfaces={key: surface.model_dump(mode="json") for key, surface in projection.surfaces.items()},
            route_traces=[],
            diagnostics=projection.diagnostics,
        )

    async def stream(self, context: dict[str, Any] | None = None) -> AsyncIterator[RouteDeckEvent]:
        yield build_projection_update_event(state=await self.snapshot(context))

    def state_from_context(self, context: dict[str, Any]) -> StateT:
        state = context.get("state")
        if isinstance(state, self.State):
            return state
        return self.State(node=str(context.get("node_id") or self.initial_node))

    def state_from_graph_state(self, graph_state: dict[str, Any]) -> StateT:
        if graph_state:
            return self.State.model_validate(graph_state)
        return self.State(node=self.initial_node)

    async def prepare_state(self, context: dict[str, Any]) -> StateT:
        return self.state_from_context(context)

    async def prepare_dispatch_state(
        self,
        request: RouteDeckDispatchInput,
        context: dict[str, Any],
    ) -> StateT:
        return self.state_from_graph_state(request.graph_state)

    async def project_state(
        self,
        state: StateT,
        *,
        context: dict[str, Any],
        projection_version: int = 1,
    ) -> RouteDeckProjection:
        return self._project(state, projection_version=projection_version)

    async def runtime_state_from_state(
        self,
        *,
        state: StateT,
        context: dict[str, Any],
        projection_version: int = 1,
    ) -> RouteDeckRuntimeState:
        projection = await self.project_state(
            state,
            context=context,
            projection_version=projection_version,
        )
        self.sync_state_from_projection(state, projection)
        return build_runtime_state(
            projection=projection,
            graph_state=state.model_dump(mode="json"),
            location=self.location_for_state(state, context),
            metadata=self.runtime_metadata_for_state(state, context),
        )

    def projection_version_from_context(self, context: dict[str, Any]) -> int:
        raw = context.get("projection_version")
        return raw if isinstance(raw, int) and raw >= 1 else 1

    def base_location_for_state(self, state: StateT, context: dict[str, Any]) -> str | None:
        return None

    def location_for_state(self, state: StateT, context: dict[str, Any]) -> str | None:
        return self.location_with_surface_id(
            self.base_location_for_state(state, context),
            self._navigation.resolved_surface_id(state),
        )

    def location_with_surface_id(self, location: str | None, surface_id: str | None) -> str | None:
        if not location or not surface_id:
            return location
        parts = urlsplit(location)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["surface_id"] = surface_id
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query),
                parts.fragment,
            )
        )

    def runtime_metadata_for_state(self, state: StateT, context: dict[str, Any]) -> dict[str, Any]:
        return {}

    def dispatch_metadata_for_state(self, state: StateT, context: dict[str, Any]) -> dict[str, Any]:
        return {}

    def is_route_action_id(self, action_id: str) -> bool:
        return action_id in {
            self.route_action_ids.open_node,
            self.route_action_ids.switch_surface,
            self.route_action_ids.back,
            self.route_action_ids.forward,
            self.route_action_ids.cancel,
        }

    def route_actions_for_state(self, state: StateT) -> list[Any]:
        action_ids = [
            self.route_action_ids.open_node,
            self.route_action_ids.switch_surface,
        ]
        if state.navigation_back_stack:
            action_ids.append(self.route_action_ids.back)
        if state.navigation_forward_stack:
            action_ids.append(self.route_action_ids.forward)
        if self._navigation.cancel_target_location(state):
            action_ids.append(self.route_action_ids.cancel)
        return [
            self._action_by_id[action_id]
            for action_id in action_ids
            if action_id in self._action_by_id
        ]

    def presentation_state_key(self, state: StateT, context: dict[str, Any]) -> str:
        return state.node

    def stored_presentation_state_for_state(self, state: StateT, context: dict[str, Any]) -> dict[str, Any]:
        return self._presentation_state_by_key.get(self.presentation_state_key(state, context), {})

    def store_surface_intent_for_state(
        self,
        state: StateT,
        surface_intent: Any,
        context: dict[str, Any],
    ) -> bool:
        current = self._presentation_state_by_key.setdefault(
            self.presentation_state_key(state, context),
            {},
        )
        return self._surface_registry.store_surface_intent_for_node(
            node_id=state.node,
            surface_intent=surface_intent,
            node_by_id=self._node_by_id,
            presentation_state=current,
        )

    def surface_navigation_id_from_intent(self, surface_intent: Any) -> str | None:
        if not isinstance(surface_intent, dict):
            return None
        surface_id = surface_intent.get("surface_id")
        return surface_id if isinstance(surface_id, str) and surface_id else None

    def surface_variant_intent_from_intent(self, surface_intent: Any) -> dict[str, str]:
        if not isinstance(surface_intent, dict):
            return {}
        return {
            key: value
            for key, value in surface_intent.items()
            if key != "surface_id" and isinstance(key, str) and isinstance(value, str)
        }

    def sync_state_from_projection(self, state: StateT, projection: RouteDeckProjection) -> None:
        state.active_surface_id = projection.navigation.current.surface_id

    def should_stage_operation_review(
        self,
        *,
        state: StateT,
        operation: RouteDeckOperation,
        context: dict[str, Any],
    ) -> bool:
        return operation.execution_mode != "auto" and state.pending_operation_id != operation.id

    def active_surfaces(self, state: StateT) -> list[RouteDeckSurface]:
        return []

    def frame_surfaces(self, state: StateT) -> list[RouteDeckSurface]:
        return []

    def review_surface_props(self, state: StateT) -> dict[str, Any]:
        return {}

    async def execute_action(
        self,
        operation_id: str,
        state: StateT,
        payload: dict[str, Any],
    ) -> RouteDeckActionResult[StateT, MessageT]:
        raise NotImplementedError(operation_id)

    async def execute_action_with_context(
        self,
        operation_id: str,
        state: StateT,
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> RouteDeckActionResult[StateT, MessageT]:
        return await self.execute_action(operation_id, state, payload)

    def _project(self, state: StateT, *, projection_version: int = 1) -> RouteDeckProjection:
        surfaces = [
            *self.frame_surfaces(state),
            *self._active_surfaces_with_review(state),
        ]
        state.active_surface_id = self._resolved_surface_id(state, surfaces)
        operations = [
            self._operation_policy.operation_for_action(action)
            for action in self._actions_for_state(state)
        ]
        return build_projection(
            self.manifest,
            current_node=state.node,
            operations=operations,
            surfaces=surfaces,
            navigation={
                "current": self._navigation.current_location(state).model_dump(mode="json"),
                "back_stack": [location.model_dump(mode="json") for location in state.navigation_back_stack],
                "forward_stack": [location.model_dump(mode="json") for location in state.navigation_forward_stack],
            },
            presentation_state={"context": state.node},
            projection_version=projection_version,
            diagnostics={"source": "routedeck_runtime"},
        )

    def _runtime_state(
        self,
        *,
        state: StateT,
        projection_version: int = 1,
    ) -> RouteDeckRuntimeState:
        projection = self._project(state, projection_version=projection_version)
        return build_runtime_state(
            projection=projection,
            graph_state=state.model_dump(mode="json"),
        )

    def _dispatch_result(
        self,
        *,
        operation_id: str,
        state: RouteDeckRuntimeState,
        messages: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RouteDeckDispatchResult:
        return build_dispatch_result(
            operation_id=operation_id,
            state=state,
            active_surface=self._active_surface_from_projection(state.projection),
            messages=messages,
            metadata=metadata,
        )

    def _active_surfaces_with_review(self, state: StateT) -> list[RouteDeckSurface]:
        surfaces = list(self.active_surfaces(state))
        if not state.pending_operation_id:
            return surfaces
        review_surface = self._surface_registry.operation_review_surface(
            node_id=state.node,
            operation_id=state.pending_operation_id,
            operation_args=state.pending_operation_args,
            component=self.operation_review_component,
            props=self.review_surface_props(state),
        )
        return [review_surface, *surfaces]

    def _resolved_surface_id(self, state: StateT, surfaces: list[RouteDeckSurface]) -> str | None:
        active_surface_ids = [
            surface.surface_id
            for surface in surfaces
            if surface.role == "active" and surface.surface_id
        ]
        if state.active_surface_id in active_surface_ids:
            return state.active_surface_id
        if state.pending_operation_id:
            review_surface_id = self._surface_registry.operation_review_surface_id(state.pending_operation_id)
            if review_surface_id in active_surface_ids:
                return review_surface_id
        return active_surface_ids[0] if active_surface_ids else None

    def _active_surface_from_projection(self, projection: RouteDeckProjection) -> RouteDeckSurface | None:
        return self._navigation.active_surface_from_projection(projection)

    def _actions_for_state(self, state: StateT) -> list[Any]:
        node = self._node_by_id.get(state.node)
        if node is None:
            return []
        actions = [
            self._action_by_id[action_id]
            for action_id in node.allowed_actions
            if action_id in self._action_by_id
        ]
        if state.navigation_forward_stack and self.route_action_ids.forward in self._action_by_id:
            actions.append(self._action_by_id[self.route_action_ids.forward])
        if self.route_action_ids.cancel in self._action_by_id and self._navigation.cancel_target_location(state):
            actions.append(self._action_by_id[self.route_action_ids.cancel])
        return actions

    def _target_nodes_by_action(self) -> dict[str, str]:
        return {
            edge.action_id: edge.to_stage
            for edge in self.manifest.edges
            if edge.action_id
        }

    def _next_projection_version(self, request: RouteDeckDispatchInput) -> int:
        return (request.projection_version or 1) + 1


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
    capabilities: list[RouteDeckCapabilitySpec] | None = None,
    navgraph: RouteDeckNavGraph | dict[str, Any] | None = None,
    available_entities: list[RouteDeckAvailableEntity] | None = None,
    surface_affordances: list[RouteDeckSurfaceAffordance] | None = None,
    context_lens: RouteDeckContextLens | dict[str, Any] | None = None,
    projection_version: int = 1,
    diagnostics: dict[str, Any] | None = None,
) -> RouteDeckProjection:
    node = next((candidate for candidate in manifest.nodes if candidate.id == current_node), None)
    surface_map: dict[str, RouteDeckSurface] = {}
    for surface in surfaces or []:
        coerced = _coerce_surface_variant(surface, node)
        key = coerced.name if coerced.name not in surface_map else (coerced.surface_id or coerced.name)
        surface_map[key] = coerced
    navigation_state = _coerce_navigation(current_node=current_node, navigation=navigation)
    legal_operations = [operation for operation in operations or [] if operation.execution_mode != "blocked"]
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
        capabilities=capabilities if capabilities is not None else list(manifest.capabilities),
        navgraph=_coerce_navgraph(manifest=manifest, current_node=current_node, navigation=navigation_state, navgraph=navgraph),
        available_entities=available_entities or [],
        surface_affordances=surface_affordances or [],
        diagnostics=diagnostics or {},
    )


def build_dispatch_state_event(
    *,
    operation_id: str,
    state: RouteDeckRuntimeState,
    event_type: RouteDeckEventType = "operation_completed",
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
        projection_version=projection_version if projection_version is not None else state.projection.projection_version,
        payload=event_payload,
    )


def build_runtime_state(
    *,
    projection: RouteDeckProjection,
    status: str = "idle",
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
        diagnostics=dict(projection.diagnostics if diagnostics is None else diagnostics),
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
        projection_version=projection_version if projection_version is not None else state.projection.projection_version,
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
        projection_version=projection_version if projection_version is not None else projection.projection_version,
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
            "active_surface": active_surface.model_dump(mode="json") if active_surface else None,
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
        events=list(events) if events is not None else [
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
        state = RouteDeckNavigationState(current=RouteDeckLocation(node_id=current_node))
    return state.model_copy(
        update={
            "can_back": bool(state.back_stack),
            "can_forward": bool(state.forward_stack),
            "can_cancel": bool(state.back_stack or state.current.node_id != current_node),
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
                from_stage=edge.from_stage,
                to=edge.to_stage,
                action_id=edge.action_id,
                capability_id=edge.capability_id,
            )
            for edge in manifest.edges
        ],
        reachable=reachable_nodes(manifest, current_node),
    )
