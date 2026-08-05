from __future__ import annotations

from routedeck_core.contracts.navigation import (
    NodeRef,
)
from routedeck_core.contracts.operations import (
    EntityInput,
    EntityProvider,
    Guard,
    Operation,
    OperationSource,
    SafetyClass,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.surfaces import (
    SurfaceAffordance,
    SurfaceRef,
)

from ...identifiers import (
    MedusaOperationType,
    MedusaOutcomeType,
)

from .models import (
    CATALOG_COLLECTION_PROVIDER_SCHEMA,
    CATALOG_COLLECTION_SCHEMA,
    CATALOG_PRODUCT_PROVIDER_SCHEMA,
    CATALOG_PRODUCT_SCHEMA,
    CATALOG_SELECTION_SCHEMA,
)

CATALOG_PRODUCTS_PROVIDER = EntityProvider(
    id="catalog.products",
    entity_kind="product",
    description="Display-safe products and prices for the current buyer market.",
    output_schema=FrozenJsonObject(CATALOG_COLLECTION_PROVIDER_SCHEMA),
)
CATALOG_PRODUCT_PROVIDER = EntityProvider(
    id="catalog.product",
    entity_kind="product",
    description="One product, its variants, prices, and inventory facts.",
    output_schema=FrozenJsonObject(CATALOG_PRODUCT_PROVIDER_SCHEMA),
)
CATALOG_VARIANTS_PROVIDER = EntityProvider(
    id="catalog.variants",
    entity_kind="variant",
    description="Opaque variant bindings for the current product.",
    output_schema=FrozenJsonObject(CATALOG_PRODUCT_SCHEMA),
)
PUBLIC_PRODUCT_GUARD = Guard(
    id="catalog.public_product",
    description="Requires a caller-validated public product handle.",
)
VARIANT_ALLOWED_GUARD = Guard(
    id="catalog.variant_allowed",
    description="Requires a variant from the current product allowlist.",
)

CATALOG_LIST = Operation(
    id=MedusaOperationType.CATALOG_LIST,
    title="Browse products",
    description=(
        "Load the authoritative product collection when the current buyer turn "
        "requests the catalog or available product facts. This operation must not "
        "run merely because it is legal or was used in a prior turn."
    ),
    input_schema=FrozenJsonObject(
        {"type": "object", "properties": {}, "additionalProperties": False}
    ),
    safety_class=SafetyClass.READ_EXTERNAL,
    allowed_sources=frozenset(
        {OperationSource.AGENT, OperationSource.ROUTE, OperationSource.SURFACE}
    ),
    outcomes=(MedusaOutcomeType.LISTED,),
    outcome_schemas=FrozenJsonObject({"listed": CATALOG_COLLECTION_SCHEMA}),
    provider_refs=(CATALOG_PRODUCTS_PROVIDER.ref,),
)
CATALOG_SEARCH = Operation(
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
    allowed_sources=frozenset({OperationSource.AGENT, OperationSource.SURFACE}),
    outcomes=(MedusaOutcomeType.SEARCHED,),
    outcome_schemas=FrozenJsonObject({"searched": CATALOG_COLLECTION_SCHEMA}),
    provider_refs=(CATALOG_PRODUCTS_PROVIDER.ref,),
)
OPEN_PRODUCT = Operation(
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
        EntityInput(argument_name="product_ref", entity_kind="product"),
    ),
    safety_class=SafetyClass.NAVIGATION,
    allowed_sources=frozenset({OperationSource.AGENT, OperationSource.SURFACE}),
    outcomes=(MedusaOutcomeType.OPENED,),
    outcome_schemas=FrozenJsonObject({"opened": CATALOG_PRODUCT_SCHEMA}),
    provider_refs=(CATALOG_PRODUCT_PROVIDER.ref,),
    guard_refs=(PUBLIC_PRODUCT_GUARD.ref,),
)
OPEN_PRODUCT_BY_ROUTE = Operation(
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
    allowed_sources=frozenset({OperationSource.ROUTE}),
    outcomes=(MedusaOutcomeType.OPENED,),
    outcome_schemas=FrozenJsonObject({"opened": CATALOG_PRODUCT_SCHEMA}),
    provider_refs=(CATALOG_PRODUCT_PROVIDER.ref,),
)
SELECT_VARIANT = Operation(
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
        EntityInput(argument_name="variant_ref", entity_kind="variant"),
    ),
    safety_class=SafetyClass.STATE_SELECTION,
    allowed_sources=frozenset({OperationSource.AGENT, OperationSource.SURFACE}),
    outcomes=(MedusaOutcomeType.SELECTED,),
    outcome_schemas=FrozenJsonObject({"selected": CATALOG_SELECTION_SCHEMA}),
    provider_refs=(CATALOG_VARIANTS_PROVIDER.ref,),
    guard_refs=(VARIANT_ALLOWED_GUARD.ref,),
)
CONTINUE_SHOPPING = Operation(
    id=MedusaOperationType.CATALOG_CONTINUE_SHOPPING,
    title="Continue shopping",
    description="Return to catalog browsing after confirmation.",
    safety_class=SafetyClass.NAVIGATION,
    allowed_sources=frozenset({OperationSource.AGENT, OperationSource.SURFACE}),
    outcomes=(MedusaOutcomeType.CONTINUED,),
    outcome_schemas=FrozenJsonObject({"continued": CATALOG_COLLECTION_SCHEMA}),
    provider_refs=(CATALOG_PRODUCTS_PROVIDER.ref,),
)
CONTINUE_SHOPPING_AFFORDANCE = SurfaceAffordance(
    id="continue_shopping",
    event="open",
    operation=CONTINUE_SHOPPING.ref,
)

BUYER_HOME_REF = NodeRef(id="buyer.home")
CATALOG_BROWSE_REF = NodeRef(id="catalog.browse")
CATALOG_PRODUCT_REF = NodeRef(id="catalog.product")
PRODUCT_DETAIL_REF = SurfaceRef(id="catalog.product_detail")
