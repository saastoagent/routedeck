from __future__ import annotations

from routedeck_core.app import FeatureSpec
from routedeck_core.contracts.application import (
    CapabilitySpec,
    NodeSpec,
    RouteEntrySpec,
    RouteParameterBinding,
)
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    RecoveryPolicySpec,
    RouteSpec,
    TransitionSpec,
)
from routedeck_core.contracts.operations import (
    EntityInputSpec,
    EntityProviderSpec,
    GuardSpec,
    OperationSpec,
    SafetyClass,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.surfaces import (
    SurfaceAffordanceSpec,
    SurfaceLifecycle,
    SurfaceSlotsSpec,
    SurfaceSpec,
)
from routedeck_core.contracts.suggestions import SuggestedActionSpec

from ...identifiers import (
    MedusaOperationType,
    MedusaOutcomeType,
    MedusaSuggestedActionType,
)

from .models import (
    CATALOG_COLLECTION_PROVIDER_SCHEMA,
    CATALOG_COLLECTION_SCHEMA,
    CATALOG_PRODUCT_PROVIDER_SCHEMA,
    CATALOG_PRODUCT_SCHEMA,
    CATALOG_SELECTION_SCHEMA,
)

CATALOG_PRODUCTS_PROVIDER = EntityProviderSpec(
    id="catalog.products",
    entity_kind="product",
    description="Display-safe products and prices for the current buyer market.",
    output_schema=FrozenJsonObject(CATALOG_COLLECTION_PROVIDER_SCHEMA),
)
CATALOG_PRODUCT_PROVIDER = EntityProviderSpec(
    id="catalog.product",
    entity_kind="product",
    description="One product, its variants, prices, and inventory facts.",
    output_schema=FrozenJsonObject(CATALOG_PRODUCT_PROVIDER_SCHEMA),
)
CATALOG_VARIANTS_PROVIDER = EntityProviderSpec(
    id="catalog.variants",
    entity_kind="variant",
    description="Opaque variant bindings for the current product.",
    output_schema=FrozenJsonObject(CATALOG_PRODUCT_SCHEMA),
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
    id=MedusaOperationType.CATALOG_LIST,
    title="Browse products",
    description="Load the authoritative product collection for browsing.",
    input_schema=FrozenJsonObject(
        {"type": "object", "properties": {}, "additionalProperties": False}
    ),
    safety_class=SafetyClass.READ_EXTERNAL,
    outcomes=(MedusaOutcomeType.LISTED,),
    outcome_schemas=FrozenJsonObject({"listed": CATALOG_COLLECTION_SCHEMA}),
    provider_refs=(CATALOG_PRODUCTS_PROVIDER.ref,),
)
CATALOG_SEARCH = OperationSpec(
    id=MedusaOperationType.CATALOG_SEARCH,
    title="Search products",
    description="Search the authoritative product collection.",
    input_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string", "minLength": 1}},
            "additionalProperties": False,
        }
    ),
    safety_class=SafetyClass.READ_EXTERNAL,
    outcomes=(MedusaOutcomeType.SEARCHED,),
    outcome_schemas=FrozenJsonObject({"searched": CATALOG_COLLECTION_SCHEMA}),
    provider_refs=(CATALOG_PRODUCTS_PROVIDER.ref,),
)
OPEN_PRODUCT = OperationSpec(
    id=MedusaOperationType.CATALOG_OPEN_PRODUCT,
    title="Open product",
    description=(
        "Open product detail using the exact opaque product entity handle from "
        "RouteDeck visible_entities."
    ),
    input_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": ["product_ref"],
            "properties": {
                "product_ref": {
                    "type": "string",
                    "description": (
                        "The opaque visible_entities product handle; never the "
                        "product_handle route value."
                    ),
                }
            },
            "additionalProperties": False,
        }
    ),
    entity_inputs=(
        EntityInputSpec(argument_name="product_ref", entity_kind="product"),
    ),
    safety_class=SafetyClass.NAVIGATION,
    outcomes=(MedusaOutcomeType.OPENED,),
    outcome_schemas=FrozenJsonObject({"opened": CATALOG_PRODUCT_SCHEMA}),
    provider_refs=(CATALOG_PRODUCT_PROVIDER.ref,),
    guard_refs=(PUBLIC_PRODUCT_GUARD.ref,),
)
OPEN_PRODUCT_BY_ROUTE = OperationSpec(
    id=MedusaOperationType.CATALOG_OPEN_PRODUCT_BY_ROUTE,
    title="Open product route",
    description="Resolve and open one product from its exact public route handle.",
    input_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": ["product_handle"],
            "properties": {"product_handle": {"type": "string", "minLength": 1}},
            "additionalProperties": False,
        }
    ),
    safety_class=SafetyClass.NAVIGATION,
    outcomes=(MedusaOutcomeType.OPENED,),
    outcome_schemas=FrozenJsonObject({"opened": CATALOG_PRODUCT_SCHEMA}),
    provider_refs=(CATALOG_PRODUCT_PROVIDER.ref,),
)
SELECT_VARIANT = OperationSpec(
    id=MedusaOperationType.CATALOG_SELECT_VARIANT,
    title="Select variant",
    description="Bind one current allowlisted product variant.",
    input_schema=FrozenJsonObject(
        {
            "type": "object",
            "required": ["variant_ref"],
            "properties": {"variant_ref": {"type": "string"}},
            "additionalProperties": False,
        }
    ),
    entity_inputs=(
        EntityInputSpec(argument_name="variant_ref", entity_kind="variant"),
    ),
    safety_class=SafetyClass.STATE_SELECTION,
    outcomes=(MedusaOutcomeType.SELECTED,),
    outcome_schemas=FrozenJsonObject({"selected": CATALOG_SELECTION_SCHEMA}),
    provider_refs=(CATALOG_VARIANTS_PROVIDER.ref,),
    guard_refs=(VARIANT_ALLOWED_GUARD.ref,),
)
CONTINUE_SHOPPING = OperationSpec(
    id=MedusaOperationType.CATALOG_CONTINUE_SHOPPING,
    title="Continue shopping",
    description="Return to catalog browsing after confirmation.",
    safety_class=SafetyClass.NAVIGATION,
    outcomes=(MedusaOutcomeType.CONTINUED,),
    outcome_schemas=FrozenJsonObject({"continued": CATALOG_COLLECTION_SCHEMA}),
    provider_refs=(CATALOG_PRODUCTS_PROVIDER.ref,),
)
CONTINUE_SHOPPING_AFFORDANCE = SurfaceAffordanceSpec(
    id="continue_shopping",
    event="open",
    operation=CONTINUE_SHOPPING.ref,
)

BUYER_FRAME = SurfaceSpec(
    id="buyer.frame",
    component="buyer.frame",
    lifecycle=SurfaceLifecycle.STABLE,
)
BROWSE_PRODUCTS_ACTION = SuggestedActionSpec(
    id=MedusaSuggestedActionType.BROWSE_PRODUCTS,
    operation_id=CATALOG_LIST.id,
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
            id="search_products", event="submit", operation=CATALOG_SEARCH.ref
        ),
        SurfaceAffordanceSpec(
            id="clear_search", event="clear", operation=CATALOG_LIST.ref
        ),
        SurfaceAffordanceSpec(
            id="open_product", event="open", operation=OPEN_PRODUCT.ref
        ),
    ),
    public_props_schema=FrozenJsonObject(CATALOG_COLLECTION_SCHEMA),
)
PRODUCT_DETAIL = SurfaceSpec(
    id="catalog.product_detail",
    component="catalog.product_detail",
    lifecycle=SurfaceLifecycle.STABLE,
    affordances=(
        SurfaceAffordanceSpec(
            id="select_variant", event="select", operation=SELECT_VARIANT.ref
        ),
    ),
    public_props_schema=FrozenJsonObject(CATALOG_PRODUCT_SCHEMA),
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
    entity_providers=(CATALOG_PRODUCTS_PROVIDER,),
    operations=(CATALOG_LIST,),
    capabilities=(BUYER_CAPABILITY,),
    surfaces=SurfaceSlotsSpec(
        active=None,
        frame=(BUYER_FRAME,),
        status=(CATALOG_STATUS,),
        error=(CATALOG_ERROR,),
        diagnostic=(CATALOG_DIAGNOSTIC,),
    ),
    suggested_actions=(BROWSE_PRODUCTS_ACTION,),
    recovery=RecoveryPolicySpec(
        directives=("retry_catalog",), failure_surface=CATALOG_ERROR.ref
    ),
)
CATALOG_BROWSE_NODE = NodeSpec(
    id="catalog.browse",
    title="Products",
    kind=NodeKind.SECTION,
    route=RouteSpec(template="/products", deep_link_policy=DeepLinkPolicy.SHAREABLE),
    entry=RouteEntrySpec(operation=CATALOG_LIST.ref, outcome=MedusaOutcomeType.LISTED),
    entity_providers=(CATALOG_PRODUCTS_PROVIDER, CATALOG_PRODUCT_PROVIDER),
    guards=(PUBLIC_PRODUCT_GUARD,),
    operations=(CATALOG_LIST, CATALOG_SEARCH, OPEN_PRODUCT),
    capabilities=(CATALOG_CAPABILITY,),
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
    entry=RouteEntrySpec(
        operation=OPEN_PRODUCT_BY_ROUTE.ref,
        outcome=MedusaOutcomeType.OPENED,
        bindings=(
            RouteParameterBinding(
                parameter="product_handle",
                argument="product_handle",
            ),
        ),
    ),
    entity_providers=(CATALOG_PRODUCT_PROVIDER, CATALOG_VARIANTS_PROVIDER),
    guards=(PUBLIC_PRODUCT_GUARD, VARIANT_ALLOWED_GUARD),
    operations=(OPEN_PRODUCT_BY_ROUTE, SELECT_VARIANT),
    capabilities=(CATALOG_CAPABILITY,),
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
            outcome=MedusaOutcomeType.LISTED,
            target=CATALOG_BROWSE_NODE.ref,
        ),
        TransitionSpec(
            source=CATALOG_BROWSE_NODE.ref,
            operation=CATALOG_SEARCH.ref,
            outcome=MedusaOutcomeType.SEARCHED,
            target=CATALOG_BROWSE_NODE.ref,
        ),
        TransitionSpec(
            source=CATALOG_BROWSE_NODE.ref,
            operation=OPEN_PRODUCT.ref,
            outcome=MedusaOutcomeType.OPENED,
            target=CATALOG_PRODUCT_NODE.ref,
        ),
        TransitionSpec(
            source=CATALOG_PRODUCT_NODE.ref,
            operation=OPEN_PRODUCT_BY_ROUTE.ref,
            outcome=MedusaOutcomeType.OPENED,
            target=CATALOG_PRODUCT_NODE.ref,
        ),
        TransitionSpec(
            source=CATALOG_PRODUCT_NODE.ref,
            operation=SELECT_VARIANT.ref,
            outcome=MedusaOutcomeType.SELECTED,
            target=CATALOG_PRODUCT_NODE.ref,
        ),
    ),
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
    "FEATURE_SPEC",
    "OPEN_PRODUCT",
    "OPEN_PRODUCT_BY_ROUTE",
    "PRODUCT_DETAIL",
    "PRODUCT_GRID",
    "PUBLIC_PRODUCT_GUARD",
    "SELECT_VARIANT",
    "VARIANT_ALLOWED_GUARD",
]
