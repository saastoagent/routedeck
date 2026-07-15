from __future__ import annotations

from collections.abc import Mapping

from routedeck_core.app import (
    BoundRouteDeckApp,
    CompiledRouteDeckApp,
    ContextProvider,
    FeatureBindings,
    Guard,
    OperationHandler,
    bind_app,
)
from routedeck_core.contracts.operations import GuardRef, OperationRef, ProviderRef

from .features.cart import create_cart_bindings
from .features.catalog import create_catalog_bindings
from .features.checkout import CheckoutPrivateFormReader, create_checkout_bindings
from .features.orders import create_order_bindings
from .medusa.client.protocol import MedusaStoreClient


def bind_medusa_app(
    *,
    app: CompiledRouteDeckApp,
    client: MedusaStoreClient,
    private_forms: CheckoutPrivateFormReader,
    configured_payment_provider_id: str,
    buyer_country_code: str,
    handlers: Mapping[OperationRef, OperationHandler],
    providers: Mapping[ProviderRef, ContextProvider],
    guards: Mapping[GuardRef, Guard],
) -> BoundRouteDeckApp:
    """Compose feature-owned Medusa bindings and validate the complete app."""

    bindings = FeatureBindings.merge(
        create_catalog_bindings(client),
        create_cart_bindings(client),
        create_checkout_bindings(
            client=client,
            private_forms=private_forms,
            configured_payment_provider_id=configured_payment_provider_id,
            buyer_country_code=buyer_country_code,
        ),
        create_order_bindings(
            client=client,
            configured_payment_provider_id=configured_payment_provider_id,
        ),
        FeatureBindings(handlers=handlers, providers=providers, guards=guards),
    )
    return bind_app(app, bindings)


__all__ = ["bind_medusa_app"]
