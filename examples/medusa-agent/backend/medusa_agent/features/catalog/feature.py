from __future__ import annotations

from routedeck_core.app import FeatureSpec
from routedeck_core.contracts.application import CapabilitySpec, NodeSpec
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    RecoveryPolicySpec,
    RouteSpec,
    TransitionSpec,
)
from routedeck_core.contracts.operations import (
    ContextProviderSpec,
    EntityProviderSpec,
    GuardSpec,
    OperationSpec,
    SafetyClass,
)
from routedeck_core.contracts.surfaces import (
    SurfaceAffordanceSpec,
    SurfaceLifecycle,
    SurfaceSlotsSpec,
    SurfaceSpec,
)

from ..cart.feature import (
    BUYER_MARKET_PROVIDER,
    CART_ADD_ITEM,
    CART_CAPABILITY,
    CART_CREATE,
    CART_EXISTS_GUARD,
    CART_OPEN,
    CART_STATE_PROVIDER,
)


CATALOG_PRODUCTS_PROVIDER = ContextProviderSpec(
    id="catalog.products",
    description="Display-safe products and prices for the current buyer market.",
)
CATALOG_PRODUCT_PROVIDER = EntityProviderSpec(
    id="catalog.product",
    entity_kind="product",
    description="One product, its variants, prices, and inventory facts.",
)
PUBLIC_PRODUCT_GUARD = GuardSpec(
    id="catalog.public_product",
    description="Requires a caller-validated public product handle.",
)
VARIANT_ALLOWED_GUARD = GuardSpec(
    id="catalog.variant_allowed",
    description="Requires a variant from the current product allowlist.",
)

CATALOG_LIST = OperationSpec(
    id="catalog.list",
    title="Browse products",
    description="Load the authoritative product collection for browsing.",
    safety_class=SafetyClass.READ_EXTERNAL,
    outcomes=("listed",),
    provider_refs=(CATALOG_PRODUCTS_PROVIDER.ref,),
)
CATALOG_SEARCH = OperationSpec(
    id="catalog.search",
    title="Search products",
    description="Search the authoritative product collection.",
    input_schema={
        "type": "object",
        "required": ["query"],
        "properties": {"query": {"type": "string", "minLength": 1}},
    },
    safety_class=SafetyClass.READ_EXTERNAL,
    outcomes=("searched",),
    provider_refs=(CATALOG_PRODUCTS_PROVIDER.ref,),
)
OPEN_PRODUCT = OperationSpec(
    id="catalog.open_product",
    title="Open product",
    description="Open product detail using a validated public handle.",
    input_schema={
        "type": "object",
        "required": ["product_handle"],
        "properties": {"product_handle": {"type": "string"}},
    },
    safety_class=SafetyClass.NAVIGATION,
    outcomes=("opened",),
    guard_refs=(PUBLIC_PRODUCT_GUARD.ref,),
)
SELECT_VARIANT = OperationSpec(
    id="catalog.select_variant",
    title="Select variant",
    description="Bind one current allowlisted product variant.",
    input_schema={
        "type": "object",
        "required": ["variant_ref"],
        "properties": {"variant_ref": {"type": "string"}},
    },
    safety_class=SafetyClass.STATE_SELECTION,
    outcomes=("selected",),
    provider_refs=(CATALOG_PRODUCT_PROVIDER.ref,),
    guard_refs=(VARIANT_ALLOWED_GUARD.ref,),
)

BUYER_FRAME = SurfaceSpec(
    id="buyer.frame",
    component="buyer.frame",
    lifecycle=SurfaceLifecycle.STABLE,
)
BUYER_WELCOME = SurfaceSpec(
    id="buyer.welcome",
    component="buyer.welcome",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordanceSpec(
            id="browse_products", event="open", operation=CATALOG_LIST.ref
        ),
    ),
)
CATALOG_FRAME = SurfaceSpec(
    id="catalog.frame",
    component="catalog.frame",
    lifecycle=SurfaceLifecycle.STABLE,
)
PRODUCT_GRID = SurfaceSpec(
    id="catalog.product_grid",
    component="catalog.product_grid",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordanceSpec(
            id="open_product", event="open", operation=OPEN_PRODUCT.ref
        ),
        SurfaceAffordanceSpec(
            id="open_cart", event="open", operation=CART_OPEN.ref
        ),
    ),
)
PRODUCT_DETAIL = SurfaceSpec(
    id="catalog.product_detail",
    component="catalog.product_detail",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordanceSpec(
            id="select_variant", event="select", operation=SELECT_VARIANT.ref
        ),
        SurfaceAffordanceSpec(
            id="create_cart", event="create", operation=CART_CREATE.ref
        ),
        SurfaceAffordanceSpec(
            id="add_item", event="add", operation=CART_ADD_ITEM.ref
        ),
        SurfaceAffordanceSpec(
            id="open_cart", event="open", operation=CART_OPEN.ref
        ),
    ),
)
CATALOG_STATUS = SurfaceSpec(
    id="catalog.status",
    component="catalog.status",
    lifecycle=SurfaceLifecycle.STABLE,
)
CATALOG_ERROR = SurfaceSpec(
    id="catalog.error",
    component="catalog.error",
    lifecycle=SurfaceLifecycle.STABLE,
)
CATALOG_DIAGNOSTIC = SurfaceSpec(
    id="catalog.diagnostic",
    component="catalog.diagnostic",
)

BUYER_CAPABILITY = CapabilitySpec(
    id="buyer.start",
    title="Start buyer journey",
    operations=(CATALOG_LIST.ref,),
    surfaces=(BUYER_WELCOME.ref,),
)
CATALOG_CAPABILITY = CapabilitySpec(
    id="catalog.browse",
    title="Browse catalog",
    operations=(
        CATALOG_LIST.ref,
        CATALOG_SEARCH.ref,
        OPEN_PRODUCT.ref,
        SELECT_VARIANT.ref,
    ),
    surfaces=(
        PRODUCT_GRID.ref,
        PRODUCT_DETAIL.ref,
        CATALOG_STATUS.ref,
        CATALOG_ERROR.ref,
        CATALOG_DIAGNOSTIC.ref,
    ),
)

BUYER_HOME_NODE = NodeSpec(
    id="buyer.home",
    title="Welcome",
    kind=NodeKind.SECTION,
    route=RouteSpec(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
    context_providers=(CATALOG_PRODUCTS_PROVIDER,),
    operations=(CATALOG_LIST,),
    capabilities=(BUYER_CAPABILITY,),
    surfaces=SurfaceSlotsSpec(
        active=BUYER_WELCOME,
        frame=(BUYER_FRAME,),
        status=(CATALOG_STATUS,),
        error=(CATALOG_ERROR,),
        diagnostic=(CATALOG_DIAGNOSTIC,),
    ),
    recovery=RecoveryPolicySpec(
        directives=("retry_catalog",), failure_surface=CATALOG_ERROR.ref
    ),
)
CATALOG_BROWSE_NODE = NodeSpec(
    id="catalog.browse",
    title="Products",
    kind=NodeKind.SECTION,
    route=RouteSpec(
        template="/products", deep_link_policy=DeepLinkPolicy.SHAREABLE
    ),
    context_providers=(CATALOG_PRODUCTS_PROVIDER, CART_STATE_PROVIDER),
    guards=(CART_EXISTS_GUARD,),
    operations=(CATALOG_LIST, CATALOG_SEARCH, OPEN_PRODUCT, CART_OPEN),
    capabilities=(CATALOG_CAPABILITY, CART_CAPABILITY),
    surfaces=SurfaceSlotsSpec(
        active=PRODUCT_GRID,
        frame=(CATALOG_FRAME,),
        peer=(PRODUCT_GRID,),
        status=(CATALOG_STATUS,),
        error=(CATALOG_ERROR,),
        diagnostic=(CATALOG_DIAGNOSTIC,),
    ),
    recovery=RecoveryPolicySpec(
        directives=("retry_catalog",), failure_surface=CATALOG_ERROR.ref
    ),
)
CATALOG_PRODUCT_NODE = NodeSpec(
    id="catalog.product",
    title="Product",
    kind=NodeKind.DETAIL,
    parent=CATALOG_BROWSE_NODE.ref,
    route=RouteSpec(
        template="/products/{product_handle}",
        deep_link_policy=DeepLinkPolicy.SHAREABLE,
    ),
    context_providers=(BUYER_MARKET_PROVIDER, CART_STATE_PROVIDER),
    entity_providers=(CATALOG_PRODUCT_PROVIDER,),
    guards=(PUBLIC_PRODUCT_GUARD, VARIANT_ALLOWED_GUARD, CART_EXISTS_GUARD),
    operations=(SELECT_VARIANT, CART_CREATE, CART_ADD_ITEM, CART_OPEN),
    capabilities=(CATALOG_CAPABILITY, CART_CAPABILITY),
    surfaces=SurfaceSlotsSpec(
        active=PRODUCT_DETAIL,
        frame=(CATALOG_FRAME,),
        detail=(PRODUCT_DETAIL,),
        status=(CATALOG_STATUS,),
        error=(CATALOG_ERROR,),
        diagnostic=(CATALOG_DIAGNOSTIC,),
    ),
    recovery=RecoveryPolicySpec(
        directives=("reload_product",), failure_surface=CATALOG_ERROR.ref
    ),
)

FEATURE_SPEC = FeatureSpec(
    namespace="catalog",
    nodes=(BUYER_HOME_NODE, CATALOG_BROWSE_NODE, CATALOG_PRODUCT_NODE),
    transitions=(
        TransitionSpec(
            source=CATALOG_BROWSE_NODE.ref,
            operation=CATALOG_LIST.ref,
            outcome="listed",
            target=CATALOG_BROWSE_NODE.ref,
        ),
        TransitionSpec(
            source=CATALOG_BROWSE_NODE.ref,
            operation=CATALOG_SEARCH.ref,
            outcome="searched",
            target=CATALOG_BROWSE_NODE.ref,
        ),
        TransitionSpec(
            source=CATALOG_BROWSE_NODE.ref,
            operation=OPEN_PRODUCT.ref,
            outcome="opened",
            target=CATALOG_PRODUCT_NODE.ref,
        ),
        TransitionSpec(
            source=CATALOG_PRODUCT_NODE.ref,
            operation=SELECT_VARIANT.ref,
            outcome="selected",
            target=CATALOG_PRODUCT_NODE.ref,
        ),
        TransitionSpec(
            source=CATALOG_PRODUCT_NODE.ref,
            operation=CART_CREATE.ref,
            outcome="created",
            target=CATALOG_PRODUCT_NODE.ref,
        ),
        TransitionSpec(
            source=CATALOG_PRODUCT_NODE.ref,
            operation=CART_ADD_ITEM.ref,
            outcome="added",
            target=CATALOG_PRODUCT_NODE.ref,
        ),
    ),
)


__all__ = [
    "BUYER_HOME_NODE",
    "CATALOG_BROWSE_NODE",
    "CATALOG_LIST",
    "CATALOG_PRODUCT_NODE",
    "FEATURE_SPEC",
]
