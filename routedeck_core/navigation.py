"""Reusable navigation mechanics for RouteDeck runtimes."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .models import (
    RouteDeckGraphNavigationLocation,
    RouteDeckGraphState,
    RouteDeckLocation,
    RouteDeckProjection,
    RouteDeckSurface,
)
from .surfaces import RouteDeckSurfaceRegistry


ROUTEDECK_PENDING_OPERATION_ID_PARAM = "__pending_operation_id"
ROUTEDECK_PENDING_OPERATION_ARGS_PARAM = "__pending_operation_args"


@dataclass(frozen=True)
class RouteDeckNavigationTransition:
    target: RouteDeckLocation
    back_stack: list[RouteDeckLocation]
    forward_stack: list[RouteDeckLocation]


class RouteDeckNavigationPolicy:
    """Framework-owned helpers for graph navigation and surface routing."""

    def active_surface_ids(self, projection: RouteDeckProjection) -> set[str]:
        return {
            surface.surface_id
            for surface in projection.surfaces.values()
            if surface.role == "active" and isinstance(surface.surface_id, str)
        }

    def active_surface_from_projection(self, projection: RouteDeckProjection) -> RouteDeckSurface | None:
        current_surface_id = projection.navigation.current.surface_id
        if current_surface_id:
            for surface in projection.surfaces.values():
                if surface.surface_id == current_surface_id:
                    return surface
        return next((surface for surface in projection.surfaces.values() if surface.role == "active"), None)

    def legal_target_node_ids(
        self,
        *,
        projection: RouteDeckProjection,
        current_node: str,
        back_stack: Sequence[Any] = (),
        forward_stack: Sequence[Any] = (),
    ) -> set[str]:
        node_ids = {current_node}
        node_ids.update(
            operation.target_node
            for operation in projection.legal_operations
            if isinstance(operation.target_node, str) and operation.target_node
        )
        node_ids.update(location.node_id for location in self._locations(back_stack) if location.node_id)
        node_ids.update(location.node_id for location in self._locations(forward_stack) if location.node_id)
        return node_ids

    def known_navigation_location(
        self,
        *,
        node_id: str,
        back_stack: Sequence[Any] = (),
        forward_stack: Sequence[Any] = (),
    ) -> RouteDeckLocation | None:
        for location in reversed(self._locations(back_stack)):
            if location.node_id == node_id:
                return location
        for location in self._locations(forward_stack):
            if location.node_id == node_id:
                return location
        return None

    def location_from_payload(
        self,
        *,
        current: Any,
        payload: Mapping[str, Any],
        preserve_current_params: bool = False,
    ) -> RouteDeckLocation:
        current_location = self.location_from(current)
        params = payload.get("params")
        next_params = dict(current_location.params if preserve_current_params else {})
        if isinstance(params, Mapping):
            next_params = dict(params)
        surface_id = payload.get("surface_id")
        return RouteDeckLocation(
            node_id=str(payload.get("node_id") or current_location.node_id),
            surface_id=str(surface_id) if surface_id is not None else current_location.surface_id,
            params=next_params,
        )

    def back_transition(
        self,
        *,
        current: Any,
        back_stack: Sequence[Any],
        forward_stack: Sequence[Any],
    ) -> RouteDeckNavigationTransition | None:
        normalized_back = self._locations(back_stack)
        if not normalized_back:
            return None
        current_location = self.location_from(current)
        target = normalized_back[-1]
        return RouteDeckNavigationTransition(
            target=target,
            back_stack=normalized_back[:-1],
            forward_stack=[current_location, *self._locations(forward_stack)],
        )

    def forward_transition(
        self,
        *,
        current: Any,
        back_stack: Sequence[Any],
        forward_stack: Sequence[Any],
    ) -> RouteDeckNavigationTransition | None:
        normalized_forward = self._locations(forward_stack)
        if not normalized_forward:
            return None
        current_location = self.location_from(current)
        target = normalized_forward[0]
        return RouteDeckNavigationTransition(
            target=target,
            back_stack=[*self._locations(back_stack), current_location],
            forward_stack=normalized_forward[1:],
        )

    def cancel_transition(
        self,
        *,
        current: Any,
        target: Any | None,
        back_stack: Sequence[Any],
        forward_stack: Sequence[Any],
    ) -> RouteDeckNavigationTransition | None:
        if target is None:
            return None
        current_location = self.location_from(current)
        target_location = self.location_from(target)
        normalized_back = self._locations(back_stack)
        if normalized_back and normalized_back[-1] == target_location:
            normalized_back = normalized_back[:-1]
        return RouteDeckNavigationTransition(
            target=target_location,
            back_stack=normalized_back,
            forward_stack=[current_location, *self._locations(forward_stack)],
        )

    def open_transition(
        self,
        *,
        current: Any,
        target: Any,
        back_stack: Sequence[Any],
    ) -> RouteDeckNavigationTransition:
        current_location = self.location_from(current)
        target_location = self.location_from(target)
        normalized_back = self._locations(back_stack)
        if current_location != target_location:
            normalized_back = [*normalized_back, current_location]
        return RouteDeckNavigationTransition(
            target=target_location,
            back_stack=normalized_back,
            forward_stack=[],
        )

    def pushed_back_stack(
        self,
        *,
        current: Any,
        previous: Any,
        back_stack: Sequence[Any],
    ) -> list[RouteDeckLocation]:
        current_location = self.location_from(current)
        previous_location = self.location_from(previous)
        normalized_back = self._locations(back_stack)
        if current_location == previous_location:
            return normalized_back
        return [*normalized_back, previous_location]

    def location_from(self, value: Any) -> RouteDeckLocation:
        if isinstance(value, RouteDeckLocation):
            return value
        if isinstance(value, Mapping):
            return RouteDeckLocation.model_validate(value)
        return RouteDeckLocation(
            node_id=str(getattr(value, "node_id")),
            surface_id=getattr(value, "surface_id", None),
            params=dict(getattr(value, "params", {}) or {}),
        )

    def _locations(self, values: Sequence[Any]) -> list[RouteDeckLocation]:
        return [self.location_from(value) for value in values]


class RouteDeckGraphNavigationController:
    """Owns generic graph-state navigation mechanics for RouteDeck apps.

    Product runtimes can subclass this to add application-specific history
    params or cancel targets, but route stack mutation, active surface fallback,
    pending operation params, and route transitions stay in RouteDeck.
    """

    def __init__(
        self,
        *,
        surface_registry: RouteDeckSurfaceRegistry,
        node_by_id: Mapping[str, Any] | None = None,
        policy: RouteDeckNavigationPolicy | None = None,
        location_factory: Callable[..., RouteDeckGraphNavigationLocation] = RouteDeckGraphNavigationLocation,
    ) -> None:
        self._surface_registry = surface_registry
        self._node_by_id = dict(node_by_id or {})
        self._policy = policy or RouteDeckNavigationPolicy()
        self._location_factory = location_factory

    def active_surface_ids(self, projection: RouteDeckProjection) -> set[str]:
        return self._policy.active_surface_ids(projection)

    def active_surface_from_projection(self, projection: RouteDeckProjection) -> RouteDeckSurface | None:
        return self._policy.active_surface_from_projection(projection)

    def legal_target_node_ids_from_projection(self, projection: RouteDeckProjection, state: RouteDeckGraphState) -> set[str]:
        return self._policy.legal_target_node_ids(
            projection=projection,
            current_node=state.node,
            back_stack=state.navigation_back_stack,
            forward_stack=state.navigation_forward_stack,
        )

    def known_navigation_location(
        self,
        state: RouteDeckGraphState,
        node_id: str,
    ) -> RouteDeckGraphNavigationLocation | None:
        location = self._policy.known_navigation_location(
            node_id=node_id,
            back_stack=state.navigation_back_stack,
            forward_stack=state.navigation_forward_stack,
        )
        return self.location_from_route_deck(location) if location else None

    def default_surface_id(self, state: RouteDeckGraphState) -> str | None:
        return self._surface_registry.default_surface_id_for(
            state.node,
            pending_operation_id=state.pending_operation_id,
        )

    def resolved_surface_id(self, state: RouteDeckGraphState) -> str | None:
        review_surface_id = self._surface_registry.operation_id_from_surface_id(state.active_surface_id)
        if review_surface_id and state.pending_operation_id != review_surface_id:
            return self.default_surface_id(state)
        return state.active_surface_id or self.default_surface_id(state)

    def history_params_for_state(self, state: RouteDeckGraphState) -> dict[str, Any]:
        params = dict(state.route_params or {})
        params.update(self.extra_history_params(state))
        if state.pending_operation_id:
            params[ROUTEDECK_PENDING_OPERATION_ID_PARAM] = state.pending_operation_id
        if state.pending_operation_args:
            params[ROUTEDECK_PENDING_OPERATION_ARGS_PARAM] = dict(state.pending_operation_args)
        return params

    def extra_history_params(self, state: RouteDeckGraphState) -> Mapping[str, Any]:
        return {}

    def apply_extra_history_params(self, state: RouteDeckGraphState, params: dict[str, Any]) -> None:
        return None

    def current_location(self, state: RouteDeckGraphState) -> RouteDeckGraphNavigationLocation:
        return self.make_location(
            node_id=state.node,
            surface_id=self.resolved_surface_id(state),
            params=self.history_params_for_state(state),
        )

    def make_location(
        self,
        *,
        node_id: str,
        surface_id: str | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> RouteDeckGraphNavigationLocation:
        return self._location_factory(
            node_id=node_id,
            surface_id=surface_id,
            params=dict(params or {}),
        )

    def location_from_route_deck(self, location: RouteDeckLocation) -> RouteDeckGraphNavigationLocation:
        return self.make_location(
            node_id=location.node_id,
            surface_id=location.surface_id,
            params=location.params,
        )

    def locations_from_route_deck(self, locations: list[RouteDeckLocation]) -> list[RouteDeckGraphNavigationLocation]:
        return [self.location_from_route_deck(location) for location in locations]

    def location_from_payload(
        self,
        state: RouteDeckGraphState,
        payload: Mapping[str, Any],
        *,
        preserve_current_params: bool = False,
    ) -> RouteDeckGraphNavigationLocation:
        return self.location_from_route_deck(
            self._policy.location_from_payload(
                current=self.current_location(state),
                payload=payload,
                preserve_current_params=preserve_current_params,
            )
        )

    def apply_location(self, state: RouteDeckGraphState, location: RouteDeckGraphNavigationLocation) -> None:
        params = dict(location.params or {})
        pending_operation_id = params.pop(ROUTEDECK_PENDING_OPERATION_ID_PARAM, None)
        pending_operation_args = params.pop(ROUTEDECK_PENDING_OPERATION_ARGS_PARAM, {})

        self.apply_extra_history_params(state, params)
        state.node = location.node_id
        state.route_params = params
        state.pending_operation_id = str(pending_operation_id) if pending_operation_id else None
        state.pending_operation_args = pending_operation_args if isinstance(pending_operation_args, dict) else {}
        state.active_surface_id = location.surface_id or self.default_surface_id(state)

    def push_navigation(self, state: RouteDeckGraphState, previous: RouteDeckGraphNavigationLocation) -> None:
        current_stack = [
            self._policy.location_from(location)
            for location in state.navigation_back_stack
        ]
        updated_stack = self._policy.pushed_back_stack(
            current=self.current_location(state),
            previous=previous,
            back_stack=state.navigation_back_stack,
        )
        if updated_stack == current_stack:
            return
        state.navigation_back_stack = self.locations_from_route_deck(updated_stack)
        state.navigation_forward_stack = []

    def cancel_target_location(self, state: RouteDeckGraphState) -> RouteDeckGraphNavigationLocation | None:
        return state.navigation_back_stack[-1] if state.navigation_back_stack else None

    def apply_transition(self, state: RouteDeckGraphState, transition: RouteDeckNavigationTransition) -> None:
        state.navigation_back_stack = self.locations_from_route_deck(transition.back_stack)
        state.navigation_forward_stack = self.locations_from_route_deck(transition.forward_stack)
        self.apply_location(state, self.location_from_route_deck(transition.target))

    def move_back(self, state: RouteDeckGraphState) -> bool:
        transition = self._policy.back_transition(
            current=self.current_location(state),
            back_stack=state.navigation_back_stack,
            forward_stack=state.navigation_forward_stack,
        )
        if transition is None:
            return False
        self.apply_transition(state, transition)
        return True

    def move_forward(self, state: RouteDeckGraphState) -> bool:
        transition = self._policy.forward_transition(
            current=self.current_location(state),
            back_stack=state.navigation_back_stack,
            forward_stack=state.navigation_forward_stack,
        )
        if transition is None:
            return False
        self.apply_transition(state, transition)
        return True

    def cancel(self, state: RouteDeckGraphState) -> bool:
        transition = self._policy.cancel_transition(
            current=self.current_location(state),
            target=self.cancel_target_location(state),
            back_stack=state.navigation_back_stack,
            forward_stack=state.navigation_forward_stack,
        )
        if transition is None:
            return False
        self.apply_transition(state, transition)
        return True

    def open_node(self, state: RouteDeckGraphState, payload: Mapping[str, Any]) -> None:
        transition = self._policy.open_transition(
            current=self.current_location(state),
            target=self.location_from_payload(state, payload, preserve_current_params=False),
            back_stack=state.navigation_back_stack,
        )
        self.apply_transition(state, transition)

    def switch_surface(self, state: RouteDeckGraphState, payload: Mapping[str, Any]) -> None:
        target = self.location_from_payload(state, payload, preserve_current_params=True)
        if state.pending_operation_id and target.surface_id != self._surface_registry.operation_review_surface_id(state.pending_operation_id):
            target.params.pop(ROUTEDECK_PENDING_OPERATION_ID_PARAM, None)
            target.params.pop(ROUTEDECK_PENDING_OPERATION_ARGS_PARAM, None)
        transition = self._policy.open_transition(
            current=self.current_location(state),
            target=target,
            back_stack=state.navigation_back_stack,
        )
        self.apply_transition(state, transition)
