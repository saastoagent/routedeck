from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from routedeck_core import (
    RouteDeckAvailableEntity,
    RouteDeckCapabilitySpec,
    RouteDeckDeepLink,
    RouteDeckEdgeSpec,
    RouteDeckLocation,
    RouteDeckManifest,
    RouteDeckNavGraph,
    RouteDeckNavGraphEdge,
    RouteDeckNavGraphNode,
    RouteDeckNavigationState,
    RouteDeckNodeSpec,
    RouteDeckProjection,
    RouteDeckSurface,
    build_projection,
)


DEFAULT_PRODUCT_HANDLE = "t-shirt"


@dataclass(frozen=True)
class MedusaProduct:
    handle: str
    title: str
    price: str
    summary: str
    colors: tuple[str, ...]
    sizes: tuple[str, ...]


@dataclass(frozen=True)
class MedusaRouteLocation:
    node_id: str
    label: str
    path: str
    surface_id: str
    product_handle: str | None = None
    surface_query_supplied: bool = False


PRODUCTS = {
    "t-shirt": MedusaProduct(
        handle="t-shirt",
        title="Medusa T-Shirt",
        price="$48.00",
        summary="Premium cotton tee with a relaxed fit.",
        colors=("Natural", "Black", "Navy"),
        sizes=("S", "M", "L"),
    ),
    "sweatshirt": MedusaProduct(
        handle="sweatshirt",
        title="Medusa Sweatshirt",
        price="$78.00",
        summary="Soft fleece sweatshirt for everyday comfort.",
        colors=("Olive", "Charcoal", "Black"),
        sizes=("S", "M", "L"),
    ),
}


def build_medusa_projection(
    *,
    path: str = "/",
    surface_id: str | None = None,
) -> RouteDeckProjection:
    location = route_location_from_url(path=path, surface_id=surface_id)
    current = RouteDeckLocation(
        node_id=location.node_id,
        surface_id=location.surface_id,
        params=_location_params(location),
        deeplink=RouteDeckDeepLink(
            url=_deeplink_for_location(location, include_surface_query=location.surface_query_supplied),
            label=location.label,
        ),
    )

    return build_projection(
        MEDUSA_MANIFEST,
        current_node=location.node_id,
        operations=[],
        surfaces=[_active_surface(location)],
        presentation_state=_presentation_state(location),
        navigation=RouteDeckNavigationState(current=current),
        capabilities=MEDUSA_MANIFEST.capabilities,
        navgraph=_navgraph_for_location(location, current),
        available_entities=_available_entities(),
        surface_affordances=[],
        diagnostics={
            "slice": "M3.3/M3.6",
            "owner": "examples/medusa-agent",
            "note": "Read-only projected surfaces and planning context; chat SSE remains the only active behavior.",
        },
    )


def route_location_from_url(*, path: str, surface_id: str | None = None) -> MedusaRouteLocation:
    normalized_path = _normalize_path(path)
    supplied_surface = surface_id.strip() if surface_id else None

    if normalized_path.startswith("/detail/"):
        handle = normalized_path.removeprefix("/detail/").split("/", 1)[0] or DEFAULT_PRODUCT_HANDLE
        canonical_path = f"/detail/{quote(handle, safe='')}"
        return MedusaRouteLocation(
            node_id="detail",
            label="Detail",
            path=canonical_path,
            surface_id=supplied_surface or "detail.product_detail",
            product_handle=handle,
            surface_query_supplied=bool(supplied_surface),
        )

    if normalized_path == "/browse" or normalized_path.startswith("/browse/"):
        return MedusaRouteLocation(
            node_id="browse",
            label="Browse",
            path="/browse",
            surface_id=supplied_surface or "browse.product_list",
            surface_query_supplied=bool(supplied_surface),
        )

    if normalized_path == "/cart" or normalized_path.startswith("/cart/"):
        return MedusaRouteLocation(
            node_id="cart",
            label="Cart",
            path="/cart",
            surface_id=supplied_surface or "cart.summary",
            surface_query_supplied=bool(supplied_surface),
        )

    return MedusaRouteLocation(
        node_id="home",
        label="Home",
        path="/",
        surface_id=supplied_surface or "home.chat",
        surface_query_supplied=bool(supplied_surface),
    )


def _normalize_path(path: str) -> str:
    if not path or not path.startswith("/"):
        return "/"
    return path.split("?", 1)[0] or "/"


def _location_params(location: MedusaRouteLocation) -> dict[str, str]:
    if location.product_handle:
        return {"product_handle": location.product_handle}
    return {}


def _presentation_state(location: MedusaRouteLocation) -> dict[str, object]:
    state: dict[str, object] = {
        "active_surface_id": location.surface_id,
        "current_node": location.node_id,
        "deeplink": _deeplink_for_location(location, include_surface_query=location.surface_query_supplied),
        "chat_suggestions": _chat_suggestions(location),
    }
    if location.product_handle:
        state["product_handle"] = location.product_handle
    return state


def _active_surface(location: MedusaRouteLocation) -> RouteDeckSurface:
    component_by_node = {
        "home": "MedusaHomeChatSurface",
        "browse": "MedusaProductListSurface",
        "detail": "MedusaProductDetailSurface",
        "cart": "MedusaCartSummarySurface",
    }
    label_by_node = {
        "home": "Medusa shopping surface",
        "browse": "Projected product surface",
        "detail": "Projected product surface",
        "cart": "Projected cart surface",
    }

    return RouteDeckSurface(
        name="active",
        surface_id=location.surface_id,
        component=component_by_node[location.node_id],
        variant=location.surface_id,
        role="active",
        surface_kind="embedded",
        label=label_by_node[location.node_id],
        default=True,
        props=_surface_props(location),
        lifecycle="stable",
    )


def _surface_props(location: MedusaRouteLocation) -> dict[str, object]:
    base: dict[str, object] = {
        "path": location.path,
        "surface_id": location.surface_id,
    }

    if location.node_id == "browse":
        return {
            **base,
            "surface_summary": "Read-only browse surface with two Medusa products.",
            "products": [_product_payload(product) for product in PRODUCTS.values()],
        }

    if location.node_id == "detail":
        product = _product_for_handle(location.product_handle)
        return {
            **base,
            "surface_summary": f"Read-only detail surface for {product.title}.",
            "product": _product_payload(product),
        }

    if location.node_id == "cart":
        return {
            **base,
            "surface_summary": "Read-only cart summary surface.",
            "cart": {
                "item_count": 0,
                "total": "$0.00",
                "summary": "No cart items are projected in this read-only slice.",
            },
        }

    return {
        **base,
        "surface_summary": "Read-only home surface for starting a Medusa shopping conversation.",
    }


def _product_for_handle(handle: str | None) -> MedusaProduct:
    return PRODUCTS.get(handle or DEFAULT_PRODUCT_HANDLE, PRODUCTS[DEFAULT_PRODUCT_HANDLE])


def _product_payload(product: MedusaProduct) -> dict[str, object]:
    return {
        "handle": product.handle,
        "title": product.title,
        "price": product.price,
        "summary": product.summary,
        "colors": list(product.colors),
        "sizes": list(product.sizes),
    }


def _available_entities() -> list[RouteDeckAvailableEntity]:
    return [
        RouteDeckAvailableEntity(
            kind="product",
            entity_key=f"product:{product.handle}",
            label=product.title,
            rendered_on=_rendered_surfaces_for_product(product.handle),
            operations=[],
            metadata={
                "handle": product.handle,
                "price": product.price,
            },
        )
        for product in PRODUCTS.values()
    ]


def _rendered_surfaces_for_product(handle: str) -> list[str]:
    if handle == DEFAULT_PRODUCT_HANDLE:
        return ["browse.product_list", "detail.product_detail"]
    return ["browse.product_list"]


def _chat_suggestions(location: MedusaRouteLocation) -> list[dict[str, str]]:
    if location.node_id == "browse":
        return [
            {
                "label": "Compare tee and sweatshirt",
                "message": "Compare the T-shirt and sweatshirt.",
            }
        ]

    if location.node_id == "detail":
        return [
            {
                "label": "Ask about this T-shirt",
                "message": "What should I know about this Medusa T-Shirt?",
            }
        ]

    if location.node_id == "cart":
        return [
            {
                "label": "Review my cart",
                "message": "Review my current cart summary.",
            }
        ]

    return [
        {
            "label": "Show me products",
            "message": "Show me products in the current Medusa catalog",
        }
    ]


def _deeplink_for_location(location: MedusaRouteLocation, *, include_surface_query: bool = False) -> str:
    if include_surface_query:
        return f"{location.path}?surface_id={quote(location.surface_id, safe='.')}"
    return location.path


def _navgraph_for_location(
    location: MedusaRouteLocation,
    current: RouteDeckLocation,
) -> RouteDeckNavGraph:
    detail_path = f"/detail/{quote(location.product_handle or DEFAULT_PRODUCT_HANDLE, safe='')}"
    nodes = [
        RouteDeckNavGraphNode(
            id="home",
            label="Home",
            surface_id="home.chat",
            deeplink=RouteDeckDeepLink(url="/", label="Home"),
        ),
        RouteDeckNavGraphNode(
            id="browse",
            label="Browse",
            surface_id="browse.product_list",
            deeplink=RouteDeckDeepLink(url="/browse", label="Browse"),
        ),
        RouteDeckNavGraphNode(
            id="detail",
            label="Detail",
            surface_id="detail.product_detail",
            deeplink=RouteDeckDeepLink(url=detail_path, label="Detail"),
        ),
        RouteDeckNavGraphNode(
            id="cart",
            label="Cart",
            surface_id="cart.summary",
            deeplink=RouteDeckDeepLink(url="/cart", label="Cart"),
        ),
    ]

    return RouteDeckNavGraph(
        current=current,
        nodes=nodes,
        edges=[
            RouteDeckNavGraphEdge(from_stage="home", to_stage="browse"),
            RouteDeckNavGraphEdge(from_stage="browse", to_stage="detail"),
            RouteDeckNavGraphEdge(from_stage="detail", to_stage="cart"),
        ],
        traversed=_traversed_nodes(location.node_id),
        reachable=_reachable_nodes(location.node_id),
    )


def _traversed_nodes(node_id: str) -> list[str]:
    if node_id == "browse":
        return ["home"]
    if node_id == "detail":
        return ["home", "browse"]
    if node_id == "cart":
        return ["home", "browse", "detail"]
    return []


def _reachable_nodes(node_id: str) -> list[str]:
    if node_id == "home":
        return ["browse"]
    if node_id == "browse":
        return ["detail"]
    if node_id == "detail":
        return ["cart"]
    return []


MEDUSA_MANIFEST = RouteDeckManifest(
    version="medusa-agent.m3.read-only-projection",
    nodes=[
        RouteDeckNodeSpec(
            id="home",
            label="Home",
            lane="shopping",
            description="Assistant-first Medusa landing context.",
            capability_id="medusa.shopping.orientation",
            allowed_surfaces={"active": ["home.chat"]},
            default_surfaces={"active": "home.chat"},
        ),
        RouteDeckNodeSpec(
            id="browse",
            label="Browse",
            lane="shopping",
            description="Read-only browse orientation for shopping discovery.",
            capability_id="medusa.shopping.orientation",
            allowed_surfaces={"active": ["browse.product_list"]},
            default_surfaces={"active": "browse.product_list"},
        ),
        RouteDeckNodeSpec(
            id="detail",
            label="Detail",
            lane="shopping",
            description="Read-only product detail orientation.",
            node_kind="detail",
            capability_id="medusa.shopping.orientation",
            allowed_surfaces={"active": ["detail.product_detail"]},
            default_surfaces={"active": "detail.product_detail"},
        ),
        RouteDeckNodeSpec(
            id="cart",
            label="Cart",
            lane="shopping",
            description="Read-only cart orientation.",
            capability_id="medusa.shopping.orientation",
            allowed_surfaces={"active": ["cart.summary"]},
            default_surfaces={"active": "cart.summary"},
        ),
    ],
    edges=[
        RouteDeckEdgeSpec(from_stage="home", to_stage="browse", edge_type="navigation"),
        RouteDeckEdgeSpec(from_stage="browse", to_stage="detail", edge_type="navigation"),
        RouteDeckEdgeSpec(from_stage="detail", to_stage="cart", edge_type="navigation"),
    ],
    actions=[],
    capabilities=[
        RouteDeckCapabilitySpec(
            capability_id="medusa.shopping.orientation",
            label="Shopping orientation",
            surface_ids=[
                "home.chat",
                "browse.product_list",
                "detail.product_detail",
                "cart.summary",
            ],
            description="Read-only context that lets the chat understand where the shopper is.",
        )
    ],
)
