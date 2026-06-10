from __future__ import annotations

from typing import Any

from routedeck_core import RouteDeckProjection


def build_planning_context(projection: RouteDeckProjection) -> dict[str, Any]:
    current = projection.navigation.current
    active_surface = projection.surfaces.get("active")
    navgraph = projection.navgraph

    return {
        "current": {
            "node_id": current.node_id,
            "surface_id": current.surface_id,
            "deeplink": current.deeplink.url if current.deeplink else "",
        },
        "reachable_nodes": list(navgraph.reachable if navgraph else []),
        "surface_options": [
            {
                "node_id": node.id,
                "label": node.label,
                "surface_id": node.surface_id,
                "deeplink": node.deeplink.url if node.deeplink else "",
            }
            for node in (navgraph.nodes if navgraph else [])
        ],
        "capabilities": [capability.label for capability in projection.capabilities],
        "available_entities": [
            {
                "kind": entity.kind,
                "entity_key": entity.entity_key,
                "label": entity.label,
            }
            for entity in projection.available_entities
        ],
        "rendered_surface": {
            "surface_id": active_surface.surface_id if active_surface else current.surface_id,
            "component": active_surface.component if active_surface else "",
            "summary": _surface_summary(active_surface.props if active_surface else {}),
            "state": _safe_surface_state(active_surface.props if active_surface else {}),
        },
    }


def planning_context_message(context: dict[str, Any]) -> str:
    current = context["current"]
    rendered_surface = context["rendered_surface"]
    reachable = ", ".join(context["reachable_nodes"]) or "none"
    entities = ", ".join(
        f"{entity['label']} ({entity['entity_key']})" for entity in context["available_entities"]
    ) or "none"
    capabilities = ", ".join(context["capabilities"]) or "none"
    surface_facts = _surface_facts(context["rendered_surface"].get("state", {}))

    return "\n".join(
        [
            "Current RouteDeck planning context:",
            f"- node: {current['node_id']}",
            f"- surface: {current['surface_id']}",
            f"- deeplink: {current['deeplink']}",
            f"- orientation-only reachable nodes: {reachable}",
            f"- rendered surface: {rendered_surface['component']} - {rendered_surface['summary']}",
            f"- rendered product facts: {surface_facts}",
            f"- available entities: {entities}",
            f"- capabilities: {capabilities}",
            "Reachable nodes are map context, not next-step recommendations or actions.",
            "Use this as read-only shopping context. Do not claim cart or account changes.",
            "Answer product facts only from rendered product facts, available entities, or tool output.",
        ]
    )


def _surface_summary(props: dict[str, Any]) -> str:
    summary = props.get("surface_summary")
    return summary if isinstance(summary, str) else ""


def _safe_surface_state(props: dict[str, Any]) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for key in ("product", "products", "cart"):
        value = props.get(key)
        if value is not None:
            state[key] = value
    return state


def _surface_facts(state: dict[str, Any]) -> str:
    products = state.get("products")
    if isinstance(products, list) and products:
        return "; ".join(_product_fact(product) for product in products if isinstance(product, dict)) or "none"

    product = state.get("product")
    if isinstance(product, dict):
        return _product_fact(product)

    cart = state.get("cart")
    if isinstance(cart, dict):
        item_count = cart.get("item_count", 0)
        total = cart.get("total", "")
        summary = cart.get("summary", "")
        return f"cart items={item_count}, total={total}, summary={summary}"

    return "none"


def _product_fact(product: dict[str, Any]) -> str:
    title = _string(product.get("title"))
    handle = _string(product.get("handle"))
    price = _string(product.get("price"))
    summary = _string(product.get("summary"))
    colors = _string_list(product.get("colors"))
    sizes = _string_list(product.get("sizes"))
    parts = [
        f"title={title}",
        f"handle={handle}",
        f"price={price}",
        f"summary={summary}",
    ]
    if colors:
        parts.append(f"colors={', '.join(colors)}")
    if sizes:
        parts.append(f"sizes={', '.join(sizes)}")
    return ", ".join(parts)


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []
