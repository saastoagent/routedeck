from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from core.config import Settings
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
from services.medusa_catalog import MedusaCatalogProduct, load_medusa_catalog


@dataclass(frozen=True)
class MedusaRouteLocation:
    node_id: str
    label: str
    path: str
    surface_id: str
    product_handle: str | None = None
    surface_query_supplied: bool = False


def build_medusa_projection(
    *,
    path: str = "/",
    surface_id: str | None = None,
    catalog_products: tuple[MedusaCatalogProduct, ...] = (),
    catalog_status: dict[str, object] | None = None,
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
        surfaces=[_active_surface(location, catalog_products, catalog_status)],
        presentation_state=_presentation_state(location, catalog_products),
        navigation=RouteDeckNavigationState(current=current),
        capabilities=MEDUSA_MANIFEST.capabilities,
        navgraph=_navgraph_for_location(location, current, catalog_products),
        available_entities=_available_entities(catalog_products),
        surface_affordances=[],
        diagnostics={
            "slice": "M3.3/M3.6/M3.7",
            "owner": "examples/medusa-agent",
            "catalog": catalog_status or {
                "ok": False,
                "source": "medusa_store_api",
                "code": "catalog_not_loaded",
                "message": "No Medusa catalog snapshot was supplied to the projection builder.",
            },
            "note": "Read-only projected surfaces and planning context; chat SSE carries assistant text and RouteDeck state SSE carries projection updates.",
        },
    )


def build_runtime_medusa_projection(
    *,
    path: str = "/",
    surface_id: str | None = None,
    settings: Settings | None = None,
) -> RouteDeckProjection:
    catalog = load_medusa_catalog(settings)
    return build_medusa_projection(
        path=path,
        surface_id=surface_id,
        catalog_products=catalog.products,
        catalog_status=catalog.status,
    )


def route_location_from_url(*, path: str, surface_id: str | None = None) -> MedusaRouteLocation:
    normalized_path = _normalize_path(path)
    supplied_surface = surface_id.strip() if surface_id else None

    if normalized_path == "/detail" or normalized_path.startswith("/detail/"):
        handle = (
            normalized_path.removeprefix("/detail/").split("/", 1)[0]
            if normalized_path.startswith("/detail/")
            else ""
        )
        canonical_path = f"/detail/{quote(handle, safe='')}" if handle else "/detail"
        return MedusaRouteLocation(
            node_id="detail",
            label="Detail",
            path=canonical_path,
            surface_id=supplied_surface or "detail.product_detail",
            product_handle=handle or None,
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


def _presentation_state(
    location: MedusaRouteLocation,
    catalog_products: tuple[MedusaCatalogProduct, ...],
) -> dict[str, object]:
    state: dict[str, object] = {
        "active_surface_id": location.surface_id,
        "current_node": location.node_id,
        "deeplink": _deeplink_for_location(location, include_surface_query=location.surface_query_supplied),
        "chat_suggestions": _chat_suggestions(location, catalog_products),
    }
    if location.product_handle:
        state["product_handle"] = location.product_handle
    return state


def _active_surface(
    location: MedusaRouteLocation,
    catalog_products: tuple[MedusaCatalogProduct, ...],
    catalog_status: dict[str, object] | None,
) -> RouteDeckSurface:
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
        props=_surface_props(location, catalog_products, catalog_status),
        lifecycle="stable",
    )


def _surface_props(
    location: MedusaRouteLocation,
    catalog_products: tuple[MedusaCatalogProduct, ...],
    catalog_status: dict[str, object] | None,
) -> dict[str, object]:
    base: dict[str, object] = {
        "path": location.path,
        "surface_id": location.surface_id,
        "catalog_status": catalog_status or {
            "ok": False,
            "source": "medusa_store_api",
            "code": "catalog_not_loaded",
        },
    }

    if location.node_id == "browse":
        if not catalog_products:
            return {
                **base,
                "surface_summary": "Medusa catalog is unavailable for read-only product projection.",
                "products": [],
            }
        return {
            **base,
            "surface_summary": f"Read-only Medusa catalog surface with {len(catalog_products)} products.",
            "products": [_product_payload(product) for product in catalog_products],
        }

    if location.node_id == "detail":
        product = _product_for_handle(location.product_handle, catalog_products)
        if not product:
            return {
                **base,
                "surface_summary": "Requested product is not available from the Medusa catalog.",
            }
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


def _product_for_handle(
    handle: str | None,
    catalog_products: tuple[MedusaCatalogProduct, ...],
) -> MedusaCatalogProduct | None:
    if not handle:
        return None
    return next((product for product in catalog_products if product.handle == handle), None)


def _product_payload(product: MedusaCatalogProduct) -> dict[str, object]:
    return {
        "handle": product.handle,
        "title": product.title,
        "price": product.price,
        "summary": product.summary,
        "colors": list(product.colors),
        "sizes": list(product.sizes),
        "image_url": product.image_url,
        "image_source": product.image_source,
    }


def _available_entities(catalog_products: tuple[MedusaCatalogProduct, ...]) -> list[RouteDeckAvailableEntity]:
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
        for product in catalog_products
    ]


def _rendered_surfaces_for_product(handle: str) -> list[str]:
    return ["browse.product_list", "detail.product_detail"]


def _chat_suggestions(
    location: MedusaRouteLocation,
    catalog_products: tuple[MedusaCatalogProduct, ...],
) -> list[dict[str, str]]:
    if location.node_id == "browse":
        return [
            {
                "label": "Show products",
                "message": "Show me products in the current Medusa catalog",
            },
            {
                "label": "Compare visible products",
                "message": "Compare the visible Medusa catalog products.",
            },
            {
                "label": "Sizing help",
                "message": "What should I consider before choosing a Medusa size?",
            },
        ]

    if location.node_id == "detail":
        product = _product_for_handle(location.product_handle, catalog_products)
        product_title = product.title if product else "this Medusa product"
        return [
            {
                "label": "Ask about this product",
                "message": f"What should I know about {product_title}?",
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
    catalog_products: tuple[MedusaCatalogProduct, ...],
) -> RouteDeckNavGraph:
    detail_handle = location.product_handle or _first_product_handle(catalog_products)
    detail_path = f"/detail/{quote(detail_handle, safe='')}" if detail_handle else "/detail"
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


def _first_product_handle(catalog_products: tuple[MedusaCatalogProduct, ...]) -> str | None:
    return catalog_products[0].handle if catalog_products else None


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
