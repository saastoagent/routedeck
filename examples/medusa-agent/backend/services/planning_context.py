from __future__ import annotations

from typing import Any

from routedeck_core import RouteDeckAvailableEntity, RouteDeckProjection


def build_medusa_planning_context(projection: RouteDeckProjection) -> str:
    active_surface = projection.surfaces.get("active")
    setup = active_surface.props.get("setup", {}) if active_surface is not None else {}
    setup_ready = bool(setup.get("ready"))
    capability_labels = [capability.label for capability in projection.capabilities if _capability_is_available(capability.operation_ids, projection)]
    capability_summary = ", ".join(capability_labels) if capability_labels else "none"

    lines = [
        "Medusa planning context:",
        f"- active surface: {active_surface.variant if active_surface is not None else 'none'}",
        f"- setup ready: {str(setup_ready).lower()}",
        f"- available capabilities: {capability_summary}",
        "- dispatch availability: unavailable when there are no available capabilities",
    ]

    entity_lines = _entity_lines(projection.available_entities)
    if entity_lines:
        lines.extend(["", "Rendered shopping entities:"])
        lines.extend(entity_lines)

    lines.extend(
        [
            "",
            "Tool policy:",
            "- Use browse_products to refresh the product list.",
            "- Use open_product with a rendered product entity key.",
            "- Use select_variant with a rendered variant entity key.",
            "- Use add_selected_variant_to_cart with a rendered variant entity key and quantity.",
            "- Use view_cart to inspect the demo cart.",
            "",
            "Shopper response policy:",
            "- Describe only products, variants, and cart items present in this planning context or returned by tools.",
            "- Do not expose entity keys, RouteDeck operation ids, graph nodes, diagnostics, dispatch traces, or endpoint paths to the shopper.",
            "- If setup is not ready, explain in product language that local demo Medusa is not connected for that capability yet.",
            "- Do not invent catalog items, prices, variants, inventory, or later-slice commerce/operator behavior.",
        ]
    )
    return "\n".join(lines)


def _capability_is_available(operation_ids: list[str], projection: RouteDeckProjection) -> bool:
    legal_ids = {operation.id for operation in projection.legal_operations}
    return any(operation_id in legal_ids for operation_id in operation_ids)


def _entity_lines(entities: list[RouteDeckAvailableEntity]) -> list[str]:
    products = [entity for entity in entities if entity.kind == "product"]
    variants_by_parent: dict[str, list[RouteDeckAvailableEntity]] = {}
    for entity in entities:
        if entity.kind != "variant" or not entity.parent_label:
            continue
        variants_by_parent.setdefault(entity.parent_label, []).append(entity)

    lines: list[str] = []
    for product in products:
        lines.append(f"- product: {_clean(product.label)} (entity_key: {product.entity_key})")
        for variant in variants_by_parent.get(product.label, []):
            lines.append(f"  - variant: {_clean(variant.label)} (entity_key: {variant.entity_key})")
    return lines


def _clean(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())
