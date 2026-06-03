from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from routedeck_core import RouteDeckDispatchInput, RouteDeckDispatchResult, RouteDeckSurface

from services.routedeck_runtime import MedusaRouteDeckRuntime


def build_agent_tools(runtime: Any | None = None, session_id: str = "default") -> list[StructuredTool]:
    route_runtime = runtime or MedusaRouteDeckRuntime()

    async def browse_products() -> str:
        return await _dispatch_summary(route_runtime, session_id, "catalog.list", {})

    async def open_product(product_ref: str) -> str:
        return await _dispatch_summary(route_runtime, session_id, "catalog.open", {"product_ref": product_ref})

    async def select_variant(variant_ref: str) -> str:
        return await _dispatch_summary(route_runtime, session_id, "variant.select", {"variant_ref": variant_ref})

    async def add_selected_variant_to_cart(variant_ref: str, quantity: int) -> str:
        return await _dispatch_summary(
            route_runtime,
            session_id,
            "cart.add_item",
            {"variant_ref": variant_ref, "quantity": quantity},
        )

    async def view_cart() -> str:
        return await _dispatch_summary(route_runtime, session_id, "cart.view", {})

    return [
        StructuredTool.from_function(
            coroutine=browse_products,
            name="browse_products",
            description="Browse available local demo products.",
        ),
        StructuredTool.from_function(
            coroutine=open_product,
            name="open_product",
            description="Open product details using a product reference.",
        ),
        StructuredTool.from_function(
            coroutine=select_variant,
            name="select_variant",
            description="Select a product variant using a variant reference.",
        ),
        StructuredTool.from_function(
            coroutine=add_selected_variant_to_cart,
            name="add_selected_variant_to_cart",
            description="Add an explicitly selected variant and quantity to the demo cart.",
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
) -> str:
    try:
        result = await runtime.dispatch(
            RouteDeckDispatchInput(operation_id=operation_id, args=args),
            context={"session_id": session_id, "source": "agent_tool"},
        )
    except ValueError as exc:
        return str(exc)

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
