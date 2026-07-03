"""Reusable operation policy for converting RouteDeck actions to operations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .models import RouteDeckOperation


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
