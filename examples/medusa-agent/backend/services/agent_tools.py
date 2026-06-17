from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from services.planning_context import build_planning_context
from services.routedeck_projection import build_runtime_medusa_projection


BROWSE_PRODUCTS_SURFACE_ID = "browse.product_list"


@tool("open_medusa_surface")
def open_medusa_surface(surface_id: str) -> str:
    """Open one validated read-only Medusa surface from the current planning context."""
    if surface_id != BROWSE_PRODUCTS_SURFACE_ID:
        return json.dumps(
            {
                "ok": False,
                "source": "medusa_agent_tool",
                "error": "unsupported_surface",
                "message": "This slice only supports opening the read-only product browse surface.",
                "surface_intent": {"surface_id": surface_id},
            }
        )

    projection = build_runtime_medusa_projection(path="/browse", surface_id=surface_id)
    payload = projection.model_dump(mode="json", by_alias=True)
    active_props = payload.get("surfaces", {}).get("active", {}).get("props", {})
    products = active_props.get("products", []) if isinstance(active_props, dict) else []
    catalog_status = active_props.get("catalog_status", {}) if isinstance(active_props, dict) else {}

    if not isinstance(products, list) or not products:
        return json.dumps(
            {
                "ok": False,
                "source": "medusa_agent_tool",
                "error": "catalog_unavailable",
                "message": _catalog_message(catalog_status),
                "surface_intent": {"surface_id": surface_id},
                "route_context": {"path": "/browse", "surface_id": surface_id},
                "catalog_status": catalog_status,
            }
        )

    return json.dumps(
        {
            "ok": True,
            "source": "medusa_agent_tool",
            "intent": "open_surface",
            "reason": "browse_products",
            "surface_intent": {"surface_id": surface_id},
            "route_context": {"path": "/browse", "surface_id": surface_id},
            "projection_version": payload.get("projection_version"),
            "observation": "Opened the read-only Medusa product browse surface with the current product facts.",
            "catalog_status": catalog_status,
            "product_facts": _product_facts(products),
            "products": products,
        }
    )


MEDUSA_AGENT_TOOLS = [open_medusa_surface]


def projection_update_from_tool_output(
    output: Any,
    route_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    content = _tool_output_content(output)
    if not content:
        return None

    try:
        tool_result = json.loads(content)
    except json.JSONDecodeError:
        return None

    if not isinstance(tool_result, dict) or not tool_result.get("ok"):
        return None
    if tool_result.get("intent") != "open_surface":
        return None

    surface_id = (
        tool_result.get("surface_intent", {}).get("surface_id")
        if isinstance(tool_result.get("surface_intent"), dict)
        else None
    )
    if surface_id != BROWSE_PRODUCTS_SURFACE_ID:
        return None

    projection = build_runtime_medusa_projection(path="/browse", surface_id=surface_id)
    projection_payload = projection.model_dump(mode="json", by_alias=True)
    planning_context = build_planning_context(projection)

    return {
        "event_type": "projection_update",
        "source": "medusa_agent_tool",
        "intent": "open_surface",
        "accepted_intent": "browse_products",
        "reason": "browse_products",
        "input_route_context": _safe_route_context(route_context),
        "route_context": {"path": "/browse", "surface_id": surface_id},
        "planning_context": planning_context,
        "surface_intent": {"surface_id": surface_id},
        "projection_version": projection_payload.get("projection_version"),
        "projection": projection_payload,
    }


def _tool_output_content(output: Any) -> str:
    if isinstance(output, str):
        return output

    content = getattr(output, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [
            item.get("text")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        return "".join(text_parts)

    return ""


def _product_facts(products: Any) -> str:
    if not isinstance(products, list) or not products:
        return "No rendered products."

    rendered: list[str] = []
    for product in products:
        if not isinstance(product, dict):
            continue
        title = _string(product.get("title"))
        price = _string(product.get("price"))
        summary = _string(product.get("summary"))
        colors = ", ".join(_string_list(product.get("colors")))
        sizes = ", ".join(_string_list(product.get("sizes")))
        image_source = _string(product.get("image_source"))
        rendered.append(
            f"{title} - {price}; {summary}; colors: {colors}; sizes: {sizes}; image_source: {image_source}."
        )
    return " ".join(item for item in rendered if item.strip())


def _catalog_message(catalog_status: Any) -> str:
    if isinstance(catalog_status, dict):
        message = catalog_status.get("message")
        if isinstance(message, str) and message:
            return message
    return "The Medusa catalog is unavailable for read-only projection."


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _safe_route_context(route_context: dict[str, Any] | None) -> dict[str, str]:
    if not route_context:
        return {}
    safe: dict[str, str] = {}
    for key in ("path", "surface_id"):
        value = route_context.get(key)
        if isinstance(value, str) and value:
            safe[key] = value
    return safe
