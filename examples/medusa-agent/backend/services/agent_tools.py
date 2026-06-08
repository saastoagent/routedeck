from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.tools import StructuredTool
from routedeck_core import RouteDeckDispatchInput, RouteDeckDispatchResult, RouteDeckEvent, RouteDeckSurface

from services.routedeck_provider import get_routedeck_runtime
from services.routedeck_runtime import MedusaRouteDeckRuntime


def build_agent_tools(
    runtime: Any | None = None,
    session_id: str = "default",
    event_sink: Callable[[RouteDeckEvent], None] | None = None,
) -> list[StructuredTool]:
    route_runtime = runtime or get_routedeck_runtime()

    async def browse_products() -> str:
        return await _dispatch_summary(route_runtime, session_id, "catalog.list", {}, event_sink)

    async def open_product(entity_key: str) -> str:
        return await _dispatch_summary(route_runtime, session_id, "catalog.open", {"entity_key": entity_key}, event_sink)

    async def select_variant(entity_key: str) -> str:
        return await _dispatch_summary(route_runtime, session_id, "variant.select", {"entity_key": entity_key}, event_sink)

    async def add_selected_variant_to_cart(entity_key: str, quantity: int) -> str:
        return await _dispatch_summary(
            route_runtime,
            session_id,
            "cart.add_item",
            {"entity_key": entity_key, "quantity": quantity},
            event_sink,
        )

    async def view_cart() -> str:
        return await _dispatch_summary(route_runtime, session_id, "cart.view", {}, event_sink)

    return [
        StructuredTool.from_function(
            coroutine=browse_products,
            name="browse_products",
            description="Browse available local demo products.",
        ),
        StructuredTool.from_function(
            coroutine=open_product,
            name="open_product",
            description="Open product details using a product entity key from the planning context.",
        ),
        StructuredTool.from_function(
            coroutine=select_variant,
            name="select_variant",
            description="Select a product variant using a variant entity key from the planning context.",
        ),
        StructuredTool.from_function(
            coroutine=add_selected_variant_to_cart,
            name="add_selected_variant_to_cart",
            description="Add a rendered variant entity key and quantity to the demo cart.",
        ),
        StructuredTool.from_function(
            coroutine=view_cart,
            name="view_cart",
            description="View the current demo cart summary.",
        ),
    ]


async def _dispatch_summary(
    runtime: Any,
    session_id: str,
    operation_id: str,
    args: dict[str, Any],
    event_sink: Callable[[RouteDeckEvent], None] | None = None,
) -> str:
    try:
        result = await runtime.dispatch(
            RouteDeckDispatchInput(operation_id=operation_id, args=args),
            context={"session_id": session_id, "source": "agent_tool"},
        )
    except ValueError as exc:
        return str(exc)

    if event_sink is not None:
        for event in result.events:
            event_sink(event)

    for message in result.messages:
        content = message.get("content")
        if isinstance(content, str) and content:
            surface_summary = _surface_summary(result)
            return f"{content} {surface_summary}" if surface_summary else content
    return "That shopping action is unavailable right now."


def _surface_summary(result: RouteDeckDispatchResult) -> str | None:
    surface = result.active_surface or result.state.projection.surfaces.get("active")
    if surface is None:
        return None

    if surface.variant == "product_list":
        return _product_list_summary(surface)
    if surface.variant == "product_detail":
        return _product_detail_summary(surface)
    if surface.variant == "cart_summary":
        return _cart_summary(surface)
    return None


def _product_list_summary(surface: RouteDeckSurface) -> str | None:
    products = surface.props.get("products")
    if not isinstance(products, list):
        return None
    titles = [_clean_text(product.get("title")) for product in products if isinstance(product, dict)]
    titles = [title for title in titles if title]
    if not titles:
        return None
    return f"Available products: {', '.join(titles)}."


def _product_detail_summary(surface: RouteDeckSurface) -> str | None:
    product = surface.props.get("product")
    if not isinstance(product, dict):
        return None
    title = _clean_text(product.get("title"))
    variants = product.get("variants")
    variant_titles = []
    if isinstance(variants, list):
        variant_titles = [_clean_text(variant.get("title")) for variant in variants if isinstance(variant, dict)]
        variant_titles = [variant_title for variant_title in variant_titles if variant_title]

    if title and variant_titles:
        return f"Product details: {title}. Options: {', '.join(variant_titles)}."
    if title:
        return f"Product details: {title}."
    return None


def _cart_summary(surface: RouteDeckSurface) -> str | None:
    cart = surface.props.get("cart")
    if not isinstance(cart, dict):
        return None
    items = cart.get("items")
    if not isinstance(items, list) or not items:
        return "Cart is empty."

    item_summaries = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"))
        quantity = item.get("quantity")
        if title and isinstance(quantity, int):
            item_summaries.append(f"{title} x {quantity}")
        elif title:
            item_summaries.append(title)

    if not item_summaries:
        return None
    return f"Cart items: {', '.join(item_summaries)}."


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text:
        return None
    return text
