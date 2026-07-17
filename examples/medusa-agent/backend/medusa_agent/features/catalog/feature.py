from __future__ import annotations

from routedeck_core.app import Feature
from routedeck_core.contracts.application import (
    Capability,
    Node,
    RouteEntry,
    RouteParameterBinding,
)
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    RecoveryPolicy,
    Route,
    Transition,
)
from routedeck_core.contracts.surfaces import (
    Surface,
    SurfaceAffordance,
    SurfaceLifecycle,
    SurfaceSlots,
)
from routedeck_core.contracts.suggestions import SuggestedAction
from routedeck_core.contracts.projection import FrozenJsonObject

from ...identifiers import MedusaOutcomeType, MedusaSuggestedActionType
from ..cart.declarations import (
    ADD_ITEM_AFFORDANCE,
    BUYER_MARKET_PROVIDER,
    CART_ABSENT_GUARD,
    CART_ADD_ITEM,
    CART_BINDING_PROVIDER,
    CART_CAPABILITY,
    CART_CREATE,
    CART_CREATE_UNKNOWN_RECOVERY,
    CART_EXISTS_GUARD,
    CART_ITEMS_PROVIDER,
    CART_MUTATION_UNKNOWN_RECOVERY,
    CART_OPEN,
    CART_STATE_PROVIDER,
    CART_SUMMARY_REF,
    CREATE_CART_AFFORDANCE,
    OPEN_CART_AFFORDANCE,
    VIEW_CART_ACTION,
)
from .declarations import (
    BUYER_HOME_REF,
    CATALOG_BROWSE_REF,
    CATALOG_LIST,
    CATALOG_PRODUCTS_PROVIDER,
    CATALOG_PRODUCT_PROVIDER,
    CATALOG_PRODUCT_REF,
    CATALOG_SEARCH,
    CATALOG_VARIANTS_PROVIDER,
    CONTINUE_SHOPPING,
    CONTINUE_SHOPPING_AFFORDANCE,
    OPEN_PRODUCT,
    OPEN_PRODUCT_BY_ROUTE,
    PRODUCT_DETAIL_REF,
    PUBLIC_PRODUCT_GUARD,
    SELECT_VARIANT,
    VARIANT_ALLOWED_GUARD,
)
from .models import CATALOG_COLLECTION_SCHEMA, CATALOG_PRODUCT_SCHEMA

BUYER_FRAME = Surface(
    id="buyer.frame",
    component="buyer.frame",
    lifecycle=SurfaceLifecycle.STABLE,
)
BROWSE_PRODUCTS_ACTION = SuggestedAction(
    id=MedusaSuggestedActionType.BROWSE_PRODUCTS,
    operation_id=CATALOG_LIST.id,
)
CATALOG_FRAME = Surface(
    id="catalog.frame",
    component="catalog.frame",
    lifecycle=SurfaceLifecycle.STABLE,
)
PRODUCT_GRID = Surface(
    id="catalog.product_grid",
    component="catalog.product_grid",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordance(
            id="search_products", event="submit", operation=CATALOG_SEARCH.ref
        ),
        SurfaceAffordance(
            id="clear_search", event="clear", operation=CATALOG_LIST.ref
        ),
        SurfaceAffordance(
            id="open_product", event="open", operation=OPEN_PRODUCT.ref
        ),
        OPEN_CART_AFFORDANCE,
    ),
    public_props_schema=FrozenJsonObject(CATALOG_COLLECTION_SCHEMA),
)
PRODUCT_DETAIL = Surface(
    id=PRODUCT_DETAIL_REF.id,
    component="catalog.product_detail",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordance(
            id="select_variant", event="select", operation=SELECT_VARIANT.ref
        ),
        CREATE_CART_AFFORDANCE,
        ADD_ITEM_AFFORDANCE,
        OPEN_CART_AFFORDANCE,
    ),
    public_props_schema=FrozenJsonObject(CATALOG_PRODUCT_SCHEMA),
)
CATALOG_STATUS = Surface(
    id="catalog.status",
    component="catalog.status",
    lifecycle=SurfaceLifecycle.STABLE,
)
CATALOG_ERROR = Surface(
    id="catalog.error",
    component="catalog.error",
    lifecycle=SurfaceLifecycle.STABLE,
)
CATALOG_DIAGNOSTIC = Surface(
    id="catalog.diagnostic",
    component="catalog.diagnostic",
)

BUYER_CAPABILITY = Capability(
    id="buyer.start",
    title="Start buyer journey",
    operations=(CATALOG_LIST.ref,),
)
CATALOG_CAPABILITY = Capability(
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

BUYER_HOME_NODE = Node(
    id="buyer.home",
    title="Welcome",
    kind=NodeKind.SECTION,
    route=Route(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
    context_providers=(BUYER_MARKET_PROVIDER,),
    entity_providers=(CATALOG_PRODUCTS_PROVIDER, CART_BINDING_PROVIDER),
    guards=(CART_ABSENT_GUARD,),
    operations=(CATALOG_LIST, CART_CREATE),
    outgoing=(
        Transition(
            operation=CART_CREATE.ref,
            outcome=MedusaOutcomeType.CREATED,
            target=BUYER_HOME_REF,
        ),
        Transition(
            operation=CATALOG_LIST.ref,
            outcome=MedusaOutcomeType.LISTED,
            target=CATALOG_BROWSE_REF,
        ),
    ),
    capabilities=(BUYER_CAPABILITY, CART_CAPABILITY),
    surfaces=SurfaceSlots(
        active=None,
        frame=(BUYER_FRAME,),
        status=(CATALOG_STATUS,),
        error=(CATALOG_ERROR,),
        diagnostic=(CATALOG_DIAGNOSTIC,),
    ),
    suggested_actions=(BROWSE_PRODUCTS_ACTION,),
    recovery=RecoveryPolicy(
        directives=("retry_catalog", CART_CREATE_UNKNOWN_RECOVERY),
        failure_surface=CATALOG_ERROR.ref,
    ),
)
CATALOG_BROWSE_NODE = Node(
    id="catalog.browse",
    title="Products",
    kind=NodeKind.SECTION,
    route=Route(template="/products", deep_link_policy=DeepLinkPolicy.SHAREABLE),
    entry=RouteEntry(operation=CATALOG_LIST.ref, outcome=MedusaOutcomeType.LISTED),
    context_providers=(CART_STATE_PROVIDER,),
    entity_providers=(
        CATALOG_PRODUCTS_PROVIDER,
        CATALOG_PRODUCT_PROVIDER,
        CART_BINDING_PROVIDER,
    ),
    guards=(PUBLIC_PRODUCT_GUARD, CART_EXISTS_GUARD),
    operations=(CATALOG_LIST, CATALOG_SEARCH, OPEN_PRODUCT, CART_OPEN),
    outgoing=(
        Transition(
            operation=CATALOG_LIST.ref,
            outcome=MedusaOutcomeType.LISTED,
            target=CATALOG_BROWSE_REF,
        ),
        Transition(
            operation=CATALOG_SEARCH.ref,
            outcome=MedusaOutcomeType.SEARCHED,
            target=CATALOG_BROWSE_REF,
        ),
        Transition(
            operation=OPEN_PRODUCT.ref,
            outcome=MedusaOutcomeType.OPENED,
            target=CATALOG_PRODUCT_REF,
        ),
        Transition(
            operation=CART_OPEN.ref,
            outcome=MedusaOutcomeType.OPENED,
            target=CART_SUMMARY_REF,
        ),
    ),
    capabilities=(CATALOG_CAPABILITY, CART_CAPABILITY),
    surfaces=SurfaceSlots(
        active=PRODUCT_GRID,
        frame=(CATALOG_FRAME,),
        peer=(PRODUCT_GRID,),
        status=(CATALOG_STATUS,),
        error=(CATALOG_ERROR,),
        diagnostic=(CATALOG_DIAGNOSTIC,),
    ),
    suggested_actions=(VIEW_CART_ACTION,),
    recovery=RecoveryPolicy(
        directives=("retry_catalog",), failure_surface=CATALOG_ERROR.ref
    ),
)
CATALOG_PRODUCT_NODE = Node(
    id="catalog.product",
    title="Product",
    kind=NodeKind.DETAIL,
    parent=CATALOG_BROWSE_NODE.ref,
    route=Route(
        template="/products/{product_handle}",
        deep_link_policy=DeepLinkPolicy.SHAREABLE,
    ),
    entry=RouteEntry(
        operation=OPEN_PRODUCT_BY_ROUTE.ref,
        outcome=MedusaOutcomeType.OPENED,
        bindings=(
            RouteParameterBinding(
                parameter="product_handle",
                argument="product_handle",
            ),
        ),
    ),
    context_providers=(BUYER_MARKET_PROVIDER, CART_STATE_PROVIDER),
    entity_providers=(
        CATALOG_PRODUCT_PROVIDER,
        CATALOG_VARIANTS_PROVIDER,
        CART_BINDING_PROVIDER,
        CART_ITEMS_PROVIDER,
    ),
    guards=(
        PUBLIC_PRODUCT_GUARD,
        VARIANT_ALLOWED_GUARD,
        CART_ABSENT_GUARD,
        CART_EXISTS_GUARD,
    ),
    operations=(
        OPEN_PRODUCT_BY_ROUTE,
        SELECT_VARIANT,
        CART_CREATE,
        CART_ADD_ITEM,
        CART_OPEN,
    ),
    outgoing=(
        Transition(
            operation=OPEN_PRODUCT_BY_ROUTE.ref,
            outcome=MedusaOutcomeType.OPENED,
            target=CATALOG_PRODUCT_REF,
        ),
        Transition(
            operation=SELECT_VARIANT.ref,
            outcome=MedusaOutcomeType.SELECTED,
            target=CATALOG_PRODUCT_REF,
        ),
        Transition(
            operation=CART_CREATE.ref,
            outcome=MedusaOutcomeType.CREATED,
            target=CATALOG_PRODUCT_REF,
        ),
        Transition(
            operation=CART_ADD_ITEM.ref,
            outcome=MedusaOutcomeType.ADDED,
            target=CATALOG_PRODUCT_REF,
        ),
        Transition(
            operation=CART_OPEN.ref,
            outcome=MedusaOutcomeType.OPENED,
            target=CART_SUMMARY_REF,
        ),
    ),
    capabilities=(CATALOG_CAPABILITY, CART_CAPABILITY),
    surfaces=SurfaceSlots(
        active=PRODUCT_DETAIL,
        frame=(CATALOG_FRAME,),
        detail=(PRODUCT_DETAIL,),
        status=(CATALOG_STATUS,),
        error=(CATALOG_ERROR,),
        diagnostic=(CATALOG_DIAGNOSTIC,),
    ),
    suggested_actions=(VIEW_CART_ACTION,),
    recovery=RecoveryPolicy(
        directives=(
            "reload_product",
            CART_CREATE_UNKNOWN_RECOVERY,
            CART_MUTATION_UNKNOWN_RECOVERY,
        ),
        failure_surface=CATALOG_ERROR.ref,
    ),
)

FEATURE = Feature(
    namespace="catalog",
    nodes=(BUYER_HOME_NODE, CATALOG_BROWSE_NODE, CATALOG_PRODUCT_NODE),
)


__all__ = [
    "BROWSE_PRODUCTS_ACTION",
    "BUYER_HOME_NODE",
    "CATALOG_BROWSE_NODE",
    "CATALOG_LIST",
    "CATALOG_PRODUCTS_PROVIDER",
    "CATALOG_PRODUCT_PROVIDER",
    "CATALOG_PRODUCT_NODE",
    "CATALOG_SEARCH",
    "CATALOG_VARIANTS_PROVIDER",
    "CONTINUE_SHOPPING",
    "CONTINUE_SHOPPING_AFFORDANCE",
    "FEATURE",
    "OPEN_PRODUCT",
    "OPEN_PRODUCT_BY_ROUTE",
    "PRODUCT_DETAIL",
    "PRODUCT_GRID",
    "PUBLIC_PRODUCT_GUARD",
    "SELECT_VARIANT",
    "VARIANT_ALLOWED_GUARD",
]
