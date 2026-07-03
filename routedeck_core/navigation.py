"""Reusable navigation mechanics for RouteDeck runtimes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .models import RouteDeckLocation, RouteDeckProjection, RouteDeckSurface


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
