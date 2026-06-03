from __future__ import annotations

from routedeck_core import RouteDeckActionSpec, RouteDeckManifest, RouteDeckNodeSpec


SLICE3_MANIFEST = RouteDeckManifest(
    version="medusa-agent-slice3",
    nodes=[
        RouteDeckNodeSpec(
            id="browse",
            label="Browse",
            lane="shopping",
            description="Show local demo Medusa products.",
            allowed_actions=["catalog.list", "catalog.open", "cart.view"],
            allowed_surfaces={"active": ["setup_status", "product_list"]},
            default_surfaces={"active": "product_list"},
        ),
        RouteDeckNodeSpec(
            id="detail",
            label="Product Detail",
            lane="shopping",
            description="Show one product and its variants.",
            allowed_actions=["catalog.open", "variant.select", "cart.view"],
            allowed_surfaces={"active": ["product_detail"]},
            default_surfaces={"active": "product_detail"},
        ),
        RouteDeckNodeSpec(
            id="cart",
            label="Cart",
            lane="shopping",
            description="Show selected demo cart items.",
            allowed_actions=["cart.create", "cart.add_item", "cart.view"],
            allowed_surfaces={"active": ["cart_summary"]},
            default_surfaces={"active": "cart_summary"},
        ),
    ],
    edges=[],
    actions=[
        RouteDeckActionSpec(id="catalog.list", label="Browse products", category="execution"),
        RouteDeckActionSpec(id="catalog.open", label="View product", category="navigation"),
        RouteDeckActionSpec(id="variant.select", label="Select variant", category="execution"),
        RouteDeckActionSpec(id="cart.create", label="Start cart", category="execution"),
        RouteDeckActionSpec(id="cart.add_item", label="Add selected item to cart", category="execution"),
        RouteDeckActionSpec(id="cart.view", label="View cart", category="navigation"),
    ],
)

SLICE2_MANIFEST = SLICE3_MANIFEST
