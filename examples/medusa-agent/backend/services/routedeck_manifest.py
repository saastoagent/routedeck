from __future__ import annotations

from routedeck_core import (
    RouteDeckActionSpec,
    RouteDeckCapabilitySpec,
    RouteDeckEdgeSpec,
    RouteDeckManifest,
    RouteDeckNodeSpec,
)


SLICE3_MANIFEST = RouteDeckManifest(
    version="medusa-agent-slice3",
    nodes=[
        RouteDeckNodeSpec(
            id="home",
            label="Home",
            lane="shopping",
            description="Start the Medusa buyer-agent session.",
            allowed_actions=["catalog.list", "cart.view"],
            allowed_surfaces={"active": ["agent_home", "setup_status"]},
            default_surfaces={"active": "agent_home"},
            capability_id="catalog.browse",
        ),
        RouteDeckNodeSpec(
            id="browse",
            label="Browse",
            lane="shopping",
            description="Show local demo Medusa products.",
            allowed_actions=["catalog.list", "catalog.open", "cart.view"],
            allowed_surfaces={"active": ["setup_status", "product_list"]},
            default_surfaces={"active": "product_list"},
            capability_id="catalog.browse",
        ),
        RouteDeckNodeSpec(
            id="detail",
            label="Product Detail",
            lane="shopping",
            description="Show one product and its variants.",
            allowed_actions=["catalog.open", "variant.select", "cart.view"],
            allowed_surfaces={"active": ["product_detail"]},
            default_surfaces={"active": "product_detail"},
            capability_id="product.configure",
        ),
        RouteDeckNodeSpec(
            id="cart",
            label="Cart",
            lane="shopping",
            description="Show selected demo cart items.",
            allowed_actions=["cart.create", "cart.add_item", "cart.view"],
            allowed_surfaces={"active": ["cart_summary"]},
            default_surfaces={"active": "cart_summary"},
            capability_id="cart.manage",
        ),
    ],
    edges=[
        RouteDeckEdgeSpec(from_stage="home", to_stage="browse", type="operation", action_id="catalog.list", capability_id="catalog.browse"),
        RouteDeckEdgeSpec(from_stage="home", to_stage="cart", type="operation", action_id="cart.view", capability_id="cart.manage"),
        RouteDeckEdgeSpec(from_stage="browse", to_stage="home", type="operation", action_id="catalog.list", capability_id="catalog.browse"),
        RouteDeckEdgeSpec(from_stage="browse", to_stage="detail", type="operation", action_id="catalog.open", capability_id="catalog.browse"),
        RouteDeckEdgeSpec(from_stage="detail", to_stage="browse", type="operation", action_id="catalog.list", capability_id="catalog.browse"),
        RouteDeckEdgeSpec(from_stage="detail", to_stage="home", type="operation", action_id="catalog.list", capability_id="catalog.browse"),
        RouteDeckEdgeSpec(from_stage="browse", to_stage="cart", type="operation", action_id="cart.view", capability_id="cart.manage"),
        RouteDeckEdgeSpec(from_stage="detail", to_stage="cart", type="operation", action_id="cart.add_item", capability_id="cart.manage"),
        RouteDeckEdgeSpec(from_stage="detail", to_stage="cart", type="operation", action_id="cart.view", capability_id="cart.manage"),
        RouteDeckEdgeSpec(from_stage="cart", to_stage="home", type="operation", action_id="catalog.list", capability_id="catalog.browse"),
        RouteDeckEdgeSpec(from_stage="cart", to_stage="browse", type="operation", action_id="catalog.list", capability_id="catalog.browse"),
    ],
    actions=[
        RouteDeckActionSpec(id="catalog.list", label="Browse products", category="execution", capability_id="catalog.browse"),
        RouteDeckActionSpec(id="catalog.open", label="View product", category="navigation", capability_id="catalog.browse"),
        RouteDeckActionSpec(id="variant.select", label="Select variant", category="execution", capability_id="product.configure"),
        RouteDeckActionSpec(id="cart.create", label="Start cart", category="execution", capability_id="cart.manage"),
        RouteDeckActionSpec(id="cart.add_item", label="Add selected item to cart", category="execution", capability_id="cart.manage"),
        RouteDeckActionSpec(id="cart.view", label="View cart", category="navigation", capability_id="cart.manage"),
    ],
    capabilities=[
        RouteDeckCapabilitySpec(
            capability_id="catalog.browse",
            label="Browse catalog",
            operation_ids=["catalog.list", "catalog.open"],
            entity_kinds=["product"],
            surface_ids=["browse.product_list", "detail.product_detail"],
            description="List local demo Medusa products and open product details.",
        ),
        RouteDeckCapabilitySpec(
            capability_id="product.configure",
            label="Choose product options",
            operation_ids=["variant.select"],
            entity_kinds=["variant"],
            surface_ids=["detail.product_detail"],
            description="Select one rendered product variant.",
        ),
        RouteDeckCapabilitySpec(
            capability_id="cart.manage",
            label="Manage demo cart",
            operation_ids=["cart.create", "cart.add_item", "cart.view"],
            entity_kinds=["variant", "cart_item"],
            surface_ids=["detail.product_detail", "cart.cart_summary"],
            description="Create, view, and add selected demo items to the cart.",
        ),
    ],
)

SLICE2_MANIFEST = SLICE3_MANIFEST
