"""Reusable surface registry mechanics for RouteDeck runtimes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .models import RouteDeckSurface


class RouteDeckSurfaceRegistry:
    """Configurable helpers for product-owned RouteDeck surfaces."""

    def __init__(
        self,
        *,
        active_components_by_node: Mapping[str, str] | None = None,
        default_surface_ids_by_node: Mapping[str, str] | None = None,
        surface_hosted_operations_by_node: Mapping[str, Iterable[str]] | None = None,
        operation_review_surface_prefix: str = "operation_review.",
    ) -> None:
        self._active_components_by_node = dict(active_components_by_node or {})
        self._default_surface_ids_by_node = dict(default_surface_ids_by_node or {})
        self._surface_hosted_operations_by_node = {
            node_id: set(operation_ids)
            for node_id, operation_ids in (surface_hosted_operations_by_node or {}).items()
        }
        self._operation_review_surface_prefix = operation_review_surface_prefix

    def active_surface_component_for_node(self, node_id: str | None) -> str | None:
        return self._active_components_by_node.get(node_id or "")

    def operation_review_surface_id(self, operation_id: str) -> str:
        return f"{self._operation_review_surface_prefix}{operation_id}"

    def operation_id_from_surface_id(self, surface_id: str | None) -> str | None:
        if not surface_id or not surface_id.startswith(self._operation_review_surface_prefix):
            return None
        operation_id = surface_id.removeprefix(self._operation_review_surface_prefix).strip()
        return operation_id or None

    def is_surface_hosted_operation(self, *, node_id: str | None, operation_id: str) -> bool:
        if not node_id:
            return False
        return operation_id in self._surface_hosted_operations_by_node.get(node_id, set())

    def default_surface_id_for(
        self,
        node_id: str | None,
        *,
        pending_operation_id: str | None = None,
    ) -> str | None:
        if pending_operation_id:
            return self.operation_review_surface_id(pending_operation_id)
        if node_id in self._default_surface_ids_by_node:
            return self._default_surface_ids_by_node[node_id]
        if self.active_surface_component_for_node(node_id) is None:
            return None
        return f"{node_id}.active"

    def build_surface(
        self,
        *,
        name: str,
        component: str,
        variant: str = "default",
        role: str = "frame",
        surface_id: str | None = None,
        slot: str | None = None,
        surface_kind: str = "embedded",
        label: str | None = None,
        default: bool = False,
        props: Mapping[str, Any] | None = None,
        lifecycle: str = "ephemeral",
    ) -> RouteDeckSurface:
        return RouteDeckSurface(
            name=name,
            surface_id=surface_id,
            component=component,
            variant=variant,
            role=role,
            slot=slot,
            surface_kind=surface_kind,
            label=label,
            default=default,
            props=dict(props or {}),
            lifecycle=lifecycle,
        )

    def build_surface_from_spec(
        self,
        spec: Any,
        *,
        variant: str | None = None,
        label: str | None = None,
        props: Mapping[str, Any] | None = None,
    ) -> RouteDeckSurface:
        """Build a RouteDeck surface from a product-owned descriptor object."""

        resolved_props = props
        if resolved_props is None:
            spec_props = getattr(spec, "props", None)
            resolved_props = dict(spec_props or {})
        return self.build_surface(
            name=getattr(spec, "name"),
            surface_id=getattr(spec, "surface_id", None),
            component=getattr(spec, "component"),
            variant=variant or getattr(spec, "variant", "default"),
            role=getattr(spec, "role", "frame"),
            slot=getattr(spec, "slot", None),
            surface_kind=getattr(spec, "surface_kind", "embedded"),
            label=label or getattr(spec, "label", None),
            props=resolved_props,
            lifecycle=getattr(spec, "lifecycle", "ephemeral"),
        )

    def operation_review_surface(
        self,
        *,
        node_id: str | None,
        operation_id: str,
        operation_args: Mapping[str, Any] | None = None,
        component: str,
        props: Mapping[str, Any] | None = None,
        label: str = "Review next step",
        title: str = "Review next step",
        variant: str = "operation_review",
        surface_kind: str = "peer",
    ) -> RouteDeckSurface:
        surface_props: dict[str, Any] = {
            "title": title,
            "node_id": node_id,
            "operation_id": operation_id,
            "operation_args": dict(operation_args or {}),
        }
        surface_props.update(dict(props or {}))
        return self.build_surface(
            name="review",
            surface_id=self.operation_review_surface_id(operation_id),
            component=component,
            variant=variant,
            role="active",
            slot="active",
            surface_kind=surface_kind,
            label=label,
            props=surface_props,
        )

    def surface_variant_for_node(
        self,
        *,
        node_id: str | None,
        presentation_state: Mapping[str, Any],
        surface_name: str,
        default: str,
        node_by_id: Mapping[str, Any],
    ) -> str:
        variants = presentation_state.get("surface_variants")
        requested = variants.get(surface_name) if isinstance(variants, dict) else None
        if not isinstance(requested, str):
            return default
        node = node_by_id.get(node_id or "")
        allowed_surfaces = getattr(node, "allowed_surfaces", None)
        allowed = allowed_surfaces.get(surface_name) if isinstance(allowed_surfaces, Mapping) else None
        return requested if not allowed or requested in allowed else default

    def store_surface_intent_for_node(
        self,
        *,
        node_id: str | None,
        surface_intent: Any,
        node_by_id: Mapping[str, Any],
        presentation_state: dict[str, Any],
    ) -> bool:
        if not isinstance(surface_intent, dict):
            return False
        node = node_by_id.get(node_id or "")
        if node is None:
            return False
        accepted: dict[str, str] = {}
        for surface_name, variant in surface_intent.items():
            if not isinstance(surface_name, str) or not isinstance(variant, str):
                continue
            allowed_surfaces = getattr(node, "allowed_surfaces", None)
            allowed = allowed_surfaces.get(surface_name) if isinstance(allowed_surfaces, Mapping) else None
            if allowed and variant not in allowed:
                continue
            accepted[surface_name] = variant
        if not accepted:
            return False
        variants = dict(presentation_state.get("surface_variants") or {})
        variants.update(accepted)
        presentation_state["surface_variants"] = variants
        return True
