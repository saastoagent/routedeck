"""Reusable operation policy for converting RouteDeck actions to operations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .models import RouteDeckGraphState, RouteDeckOperation, RouteDeckProjection
from .navigation import (
    ROUTEDECK_PENDING_OPERATION_ARGS_PARAM,
    ROUTEDECK_PENDING_OPERATION_ID_PARAM,
    RouteDeckGraphNavigationController,
)
from .surfaces import RouteDeckSurfaceRegistry


class RouteDeckOperationPolicy:
    """Maps action specs into runtime-dispatchable RouteDeck operations."""

    def __init__(
        self,
        *,
        target_nodes_by_action: Mapping[str, str] | None = None,
        review_action_ids: Sequence[str] | None = None,
        safety_class_by_category: Mapping[str, str] | None = None,
        default_safety_class: str = "navigation",
        surface_categories: Sequence[str] = ("navigation",),
    ) -> None:
        self._target_nodes_by_action = dict(target_nodes_by_action or {})
        self._review_action_ids = set(review_action_ids or [])
        self._safety_class_by_category = dict(safety_class_by_category or {})
        self._default_safety_class = default_safety_class
        self._surface_categories = set(surface_categories)

    def operation_for_action(self, action: Any) -> RouteDeckOperation:
        execution_mode = self.execution_mode_for_action(action)
        invocation_kind = self.invocation_kind_for_action(action)
        fields = list(getattr(action, "fields", []) or [])
        payload = dict(getattr(action, "payload", {}) or {})
        required_args = [field.key for field in fields if field.required]
        missing_args = [
            field.key
            for field in fields
            if field.required and field.key not in payload and getattr(field, "default", None) is None
        ]
        can_dispatch_now = invocation_kind in {"direct", "surface"} and not missing_args and execution_mode != "blocked"

        return RouteDeckOperation(
            id=action.id,
            label=action.label,
            description=action.description,
            category=action.category,
            kind=action.kind,
            placement=action.placement,
            emphasis=action.emphasis,
            safety_class=self.safety_class_for_action(action),
            execution_mode=execution_mode,
            input_schema={"fields": [field.model_dump(mode="json") for field in fields]},
            payload=payload,
            invocation_kind=invocation_kind,
            can_dispatch_now=can_dispatch_now,
            required_args=required_args,
            missing_args=missing_args,
            guard=getattr(action, "disabled_reason", None),
            target_node=self.target_node_for_action(action),
            capability_id=getattr(action, "capability_id", None),
        )

    def execution_mode_for_action(self, action: Any) -> str:
        return "review" if action.kind == "form" or action.id in self._review_action_ids else "auto"

    def safety_class_for_action(self, action: Any) -> str:
        return self._safety_class_by_category.get(getattr(action, "category", None) or "", self._default_safety_class)

    def invocation_kind_for_action(self, action: Any) -> str:
        invocation_kind = getattr(action, "invocation_kind", None)
        if invocation_kind is not None:
            return invocation_kind
        if action.kind == "form":
            return "form"
        if action.category in self._surface_categories:
            return "surface"
        return "direct"

    def target_node_for_action(self, action: Any) -> str | None:
        return self._target_nodes_by_action.get(action.id)


@dataclass(frozen=True)
class RouteDeckRouteActionIds:
    open_node: str
    switch_surface: str
    back: str
    forward: str
    cancel: str

    @property
    def stack_navigation(self) -> set[str]:
        return {self.back, self.forward, self.cancel}


class RouteDeckOperationRequestPolicy:
    """Validates generic RouteDeck operation payloads and review state."""

    def __init__(
        self,
        *,
        navigation: RouteDeckGraphNavigationController,
        surface_registry: RouteDeckSurfaceRegistry,
        route_actions: RouteDeckRouteActionIds,
    ) -> None:
        self._navigation = navigation
        self._surface_registry = surface_registry
        self._route_actions = route_actions

    def validated_payload(
        self,
        *,
        state: RouteDeckGraphState,
        operation: RouteDeckOperation,
        args: dict[str, Any] | None,
        projection: RouteDeckProjection,
    ) -> dict[str, Any]:
        if operation.id == self._route_actions.open_node:
            return self._validated_route_open_node_args(
                state=state,
                projection=projection,
                args=args,
            )
        if operation.id == self._route_actions.switch_surface:
            return self._validated_route_switch_surface_args(
                state=state,
                projection=projection,
                args=args,
            )
        if operation.id in self._route_actions.stack_navigation:
            return {}
        return self._sanitize_operation_args(operation, args)

    def review_state_for_operation(
        self,
        *,
        state: RouteDeckGraphState,
        operation: RouteDeckOperation,
        args: dict[str, Any],
    ) -> RouteDeckGraphState:
        review_state = state.model_copy(deep=True)
        current_location = self._navigation.current_location(review_state)
        review_params = dict(current_location.params)
        review_params[ROUTEDECK_PENDING_OPERATION_ID_PARAM] = operation.id
        if args:
            review_params[ROUTEDECK_PENDING_OPERATION_ARGS_PARAM] = dict(args)
        else:
            review_params.pop(ROUTEDECK_PENDING_OPERATION_ARGS_PARAM, None)
        review_location = self._navigation.make_location(
            node_id=review_state.node,
            surface_id=self._surface_registry.operation_review_surface_id(operation.id),
            params=review_params,
        )
        self._navigation.apply_location(review_state, review_location)
        self._navigation.push_navigation(review_state, current_location)
        if review_state.node not in review_state.executed_nodes:
            review_state.executed_nodes.append(review_state.node)
        return review_state

    def _sanitize_operation_args(
        self,
        operation: RouteDeckOperation,
        args: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(args, dict):
            return {}
        input_schema = operation.input_schema if isinstance(operation.input_schema, dict) else {}
        fields = input_schema.get("fields")
        if not isinstance(fields, list):
            return {}
        accepted_keys = [
            field.get("key")
            for field in fields
            if isinstance(field, dict) and isinstance(field.get("key"), str)
        ]
        return {
            key: args[key]
            for key in accepted_keys
            if isinstance(key, str) and key in args
        }

    def _validated_route_open_node_args(
        self,
        *,
        state: RouteDeckGraphState,
        projection: RouteDeckProjection,
        args: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload = args if isinstance(args, dict) else {}
        node_id = payload.get("node_id")
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("route.open_node requires a legal node_id")

        allowed_node_ids = self._navigation.legal_target_node_ids_from_projection(projection, state)
        if node_id not in allowed_node_ids:
            raise ValueError("route.open_node target is not legal from the current graph state")

        normalized: dict[str, Any] = {"node_id": node_id}
        current_location = self._navigation.current_location(state)
        known_location = self._navigation.known_navigation_location(state, node_id)
        surface_id = payload.get("surface_id")

        if node_id == current_location.node_id:
            normalized["params"] = dict(current_location.params)
            if surface_id is None:
                return normalized
            if not isinstance(surface_id, str) or surface_id not in self._navigation.active_surface_ids(projection):
                raise ValueError("route.open_node surface_id is not legal on the current node")
            normalized["surface_id"] = surface_id
            return normalized

        normalized["params"] = dict(known_location.params) if known_location else {}
        if surface_id is None:
            if known_location and known_location.surface_id:
                normalized["surface_id"] = known_location.surface_id
            return normalized

        if not isinstance(surface_id, str):
            raise ValueError("route.open_node surface_id must be a string")
        expected_surface_id = known_location.surface_id if known_location else self._surface_registry.default_surface_id_for(node_id)
        if not expected_surface_id or surface_id != expected_surface_id:
            raise ValueError("route.open_node surface_id is not legal for the requested node")
        normalized["surface_id"] = surface_id
        return normalized

    def _validated_route_switch_surface_args(
        self,
        *,
        state: RouteDeckGraphState,
        projection: RouteDeckProjection,
        args: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload = args if isinstance(args, dict) else {}
        surface_id = payload.get("surface_id")
        if not isinstance(surface_id, str) or surface_id not in self._navigation.active_surface_ids(projection):
            raise ValueError("route.switch_surface requires a projected active surface_id")
        node_id = payload.get("node_id")
        if node_id is not None and node_id != state.node:
            raise ValueError("route.switch_surface must stay on the current node")
        return {
            "node_id": state.node,
            "surface_id": surface_id,
            "params": dict(self._navigation.current_location(state).params),
        }
