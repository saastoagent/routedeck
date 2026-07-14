from __future__ import annotations

from routedeck_core.app import FeatureBindings

from ...medusa.client.protocol import MedusaStoreClient
from .feature import (
    CATALOG_LIST,
    CATALOG_PRODUCTS_PROVIDER,
    CATALOG_PRODUCT_PROVIDER,
    CATALOG_SEARCH,
    CATALOG_VARIANTS_PROVIDER,
    OPEN_PRODUCT,
    OPEN_PRODUCT_BY_ROUTE,
    PUBLIC_PRODUCT_GUARD,
    SELECT_VARIANT,
    VARIANT_ALLOWED_GUARD,
)
from .handlers import (
    ListCatalogHandler,
    OpenProductByRouteHandler,
    OpenProductHandler,
    PublicProductGuard,
    SearchCatalogHandler,
    SelectVariantHandler,
    VariantAllowedGuard,
)
from .providers import CatalogProvider, CurrentCatalogProductProvider


def create_catalog_bindings(client: MedusaStoreClient) -> FeatureBindings:
    """Bind the catalog feature to its Medusa dependency."""

    catalog = CatalogProvider(client)
    return FeatureBindings(
        handlers={
            CATALOG_LIST.ref: ListCatalogHandler(),
            CATALOG_SEARCH.ref: SearchCatalogHandler(),
            OPEN_PRODUCT.ref: OpenProductHandler(),
            OPEN_PRODUCT_BY_ROUTE.ref: OpenProductByRouteHandler(),
            SELECT_VARIANT.ref: SelectVariantHandler(),
        },
        providers={
            CATALOG_PRODUCTS_PROVIDER.ref: catalog,
            CATALOG_PRODUCT_PROVIDER.ref: catalog,
            CATALOG_VARIANTS_PROVIDER.ref: CurrentCatalogProductProvider(),
        },
        guards={
            PUBLIC_PRODUCT_GUARD.ref: PublicProductGuard(),
            VARIANT_ALLOWED_GUARD.ref: VariantAllowedGuard(),
        },
    )


__all__ = ["create_catalog_bindings"]
